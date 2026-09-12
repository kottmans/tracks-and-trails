"""The assembled application (`T-036`).

**Nothing here builds a component.** Every test calls `app.compose()` and then drives what it
returns, because this task exists for the failure that no component test can see: every Phase 1
piece passing while the application still opens an empty window. A test that constructed a
manager and a store and wired them itself would be asserting on its own wiring.

The database is real, the writer thread is real, the worker is a real spawned process
(`docs/project/TESTING.md` §6). What varies is only which program the child runs.

## Wait on the UI, never on the store

`T-013`'s ordering is *persist, then signal*, and `ARC-005` made the persisting happen on another
thread. So the writer commits a row and **then** posts a signal to the GUI thread, and in between
`store.get()` answers the new state while every widget still shows the old one. That gap is the
guarantee working, not a race.

Three tests in this file were written against the store first and each of them observed the gap:
one read `COMPLETED` from disk and asserted on a view that had not been told, another decided a
probe had failed before the manager announced it. A test about the assembled *application* waits
on what the application shows. `store.get()` is for asserting agreement afterwards.

`is_idle` has the mirror-image trap: it is true before a session starts as well as after one ends,
so spinning on it returns instantly and proves nothing.
"""

import dataclasses
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from io import StringIO
from pathlib import Path
from typing import Any, Final

import pytest
from PySide6.QtCore import QMetaMethod, QObject, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
)

from tracks_and_trails import app as application
from tracks_and_trails.core import logging as app_logging
from tracks_and_trails.core import presets
from tracks_and_trails.core import presets as core_presets
from tracks_and_trails.core import settings as core_settings
from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import DownloadRequest, Job, MediaInfo, NetworkOptions
from tracks_and_trails.core.paths import thumbnail_cache_path
from tracks_and_trails.core.settings import SettingsProblem
from tracks_and_trails.downloader import ytdlp_adapter as adapter
from tracks_and_trails.downloader.protocol import (
    Failed,
    Probed,
    Progress,
    SessionKind,
    Stage,
    Succeeded,
    WorkerFinished,
)
from tracks_and_trails.downloader.ytdlp_service import Resolution, YtdlpService
from tracks_and_trails.persistence import db
from tracks_and_trails.persistence.repositories import JobRepository
from tracks_and_trails.ui import theme as ui_theme
from tracks_and_trails.ui.main_window import MainWindow
from tracks_and_trails.ui.preset_manager import (
    NO_FFMPEG_REASON,
    PRESET_LIST_NAME,
    SET_DEFAULT_NAME,
    PresetManager,
)
from tracks_and_trails.ui.queue_view import PROGRESS_COLUMN, SIZE_COLUMN
from tracks_and_trails.ui.row_delegate import PRESET_ROLE
from tracks_and_trails.ui.row_verbs import Verb
from tracks_and_trails.ui.settings_dialog import (
    DEFAULT_PRESET_NAME,
    OUTPUT_TEMPLATE_NAME,
    OUTPUT_TEMPLATE_NOTE_NAME,
    PROXY_NAME,
    RATE_LIMIT_NAME,
    RETRIES_NAME,
    YTDLP_REVERT_NAME,
    YTDLP_UPDATE_NAME,
    YTDLP_VERSION_NAME,
    SettingsDialog,
)
from tracks_and_trails.ui.staging import RowState


class QuietYtdlp(YtdlpService):
    """A yt-dlp service that records what it was asked and spawns nothing (`T-198`).

    The real one answers `refresh()` by spawning a child and importing yt-dlp, which takes
    seconds — and `open_settings` calls it every time. Every composition test that opens the
    screen would pay for that, for an answer none of them is about.

    **It is a subclass rather than a stand-in object** so the signals, the busy state and the
    guard against two operations at once are the production ones; only the three methods that
    touch a process or the network are replaced.
    """

    def __init__(self) -> None:
        super().__init__(directory=Path("/nonexistent-in-tests"))
        self.asked: list[str] = []

    def refresh(self) -> None:
        self.asked.append("refresh")

    def install_latest_version(self) -> None:
        self.asked.append("install")

    def revert(self) -> None:
        self.asked.append("revert")


# --- children the composed application spawns -------------------------------------------------


def child_probing_then_waiting(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **kwargs: Any
) -> None:
    """A probe that answers, then a download that runs until it is cancelled.

    One function for both session kinds because the composed application chooses the kind, not
    the test — which is the point of driving the assembled thing.
    """

    if kind is SessionKind.PROBE:
        queue.put(
            Probed(
                job_id=job_id,
                media=MediaInfo(
                    url=request.url,
                    title="A video that exists",
                    uploader="Somebody",
                    duration_seconds=12,
                ),
            )
        )
        queue.put(WorkerFinished(job_id=job_id, exit_code=0))
        return

    cancel = kwargs.get("cancel")
    sent = 0
    while cancel is None or not cancel.is_set():
        sent += 1024
        queue.put(
            Progress(
                job_id=job_id,
                stage=Stage.DOWNLOADING_VIDEO,
                downloaded_bytes=sent,
                total_bytes=1024 * 100,
            )
        )
        time.sleep(0.02)
    queue.put(Failed(job_id=job_id, kind=ErrorKind.CANCELLED, message="Stopped on request."))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))


def child_probing_then_failing(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """Read the URL fine, then fail the download with a retryable error.

    **The only shape that produces a retryable queue job** under `UX-003`: a URL that will not
    read never becomes a job at all, so a failed *probe* leaves nothing for the queue's retry to
    act on. Failure has to happen after Add, which is where `REQ-018`'s retry has always lived.
    """
    if kind is SessionKind.PROBE:
        queue.put(
            Probed(job_id=job_id, media=MediaInfo(url=request.url, title="A video that exists"))
        )
        queue.put(WorkerFinished(job_id=job_id, exit_code=0))
        return
    queue.put(Failed(job_id=job_id, kind=ErrorKind.NETWORK, message="the connection dropped"))
    queue.put(WorkerFinished(job_id=job_id, exit_code=1))


def child_probing_then_succeeding(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:

    if kind is SessionKind.PROBE:
        queue.put(
            Probed(
                job_id=job_id,
                media=MediaInfo(
                    url=request.url,
                    title="A video that exists",
                ),
            )
        )
        queue.put(WorkerFinished(job_id=job_id, exit_code=0))
        return

    output = Path(request.output_directory) / "A video that exists.mp4"
    output.write_bytes(b"x" * 2048)
    queue.put(
        Progress(
            job_id=job_id, stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=1024, total_bytes=2048
        )
    )
    queue.put(Succeeded(job_id=job_id, output_path=str(output), total_bytes=2048))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))


def child_failing_to_extract(
    kind: SessionKind, job_id: str, _request: DownloadRequest, queue: Any, **_: Any
) -> None:
    queue.put(
        Failed(
            job_id=job_id,
            kind=ErrorKind.NETWORK,
            message="ERROR: Unable to download webpage: <urlopen error timed out>",
        )
    )
    queue.put(WorkerFinished(job_id=job_id, exit_code=1))


# --- fixtures ---------------------------------------------------------------------------------


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def composed(
    qapp: QApplication, tmp_path: Path, spin: Callable[..., bool]
) -> Iterator[Callable[..., application.Composition]]:
    """Build composed applications and take each one down through its own shutdown lifecycle.

    Teardown drives the real thing rather than closing handles behind its back: a test that left
    a worker running would have it attributed to whichever test ran next, and one that closed the
    connection itself would prove nothing about the order `T-036` exists to establish.
    """
    built: list[application.Composition] = []

    def build(**overrides: Any) -> application.Composition:
        overrides.setdefault("database", tmp_path / "queue.db")
        overrides.setdefault("output_directory", tmp_path / "downloads")
        overrides.setdefault("geometry_file", tmp_path / "window.toml")
        # Same reason as `geometry_file`: without it these tests read and write the real
        # `user_config_dir`, which `docs/project/TESTING.md` §5 forbids (`T-078`).
        overrides.setdefault("settings_file", tmp_path / "settings.toml")
        # See `QuietYtdlp`: the real service spawns a child on every `open_settings`.
        overrides.setdefault("ytdlp_service", QuietYtdlp())
        composition = application.compose(qapp, **overrides)
        built.append(composition)
        return composition

    yield build

    for composition in built:
        composition.shutdown.begin()
    for composition in built:
        assert spin(lambda c=composition: c.shutdown.finished, timeout=60), (
            "a composed application never finished shutting down"
        )


def shown_status(composition: application.Composition, job_id: str) -> JobStatus | None:
    """What the queue **row** says about `job_id`.

    `UX-005` removed the detail pane, so the row is the application's answer now. Still the row
    and not `composition.store`, for the reason the pane was watched before it: `T-013`'s ordering
    means the writer thread commits and *then* signals the GUI thread, so a store-based wait can
    pass in the gap before anything on screen has changed.
    """
    view = composition.window.queue_view
    if view is None:
        return None
    job = view.model.job_for(job_id)
    return job.status if job is not None else None


def concurrency_control(composition: application.Composition) -> QSpinBox:
    """The spinner a person reaches to set the limit, opened the way they open it.

    **This used to be `composition.window.concurrency_control`** — a toolbar spinner the test could
    touch without opening anything. `UX-013` moved the limit into the Settings screen (`T-234`),
    so the control now exists only while that screen is up, and reaching it means going through
    `open_settings` exactly as the menu item does.

    That keeps `T-078`'s criterion intact rather than working around it: **driven through the
    widget, never the constructor.** A test that switched to calling composition's handler
    directly when the toolbar spinner went away would satisfy every assertion below and stop
    testing the thing `P2PLAN-R3` reported.
    """
    screen = composition.window.open_settings()
    assert screen is not None, (
        "the composed window would not open its Settings screen, so there is no concurrency "
        "control to drive — composition did not wire the settings writers"
    )
    QApplication.processEvents()
    box = screen.findChild(QSpinBox, "settingsConcurrencyChoice")
    assert box is not None, "the Settings screen has no concurrency spinner"
    return box


def test_a_queued_playlist_entry_left_on_disk_is_probed_after_restart(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """`T137-R2` at the startup seam, not only the add-dialog callback.

    The durable write and the callback that admits its probe are separate operations.  If the
    application exits between them, a flat playlist entry remains `QUEUED` and unprobed on disk.
    Startup must preserve `ARC-009` rather than admitting that row directly as a download.
    """
    database = tmp_path / "queued-playlist.sqlite3"
    connection = db.connect(database)
    repository = JobRepository(connection)
    request = DownloadRequest(
        url="https://example.invalid/playlist-entry",
        output_directory=str(tmp_path / "downloads"),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )
    repository.append(
        [
            Job(
                id="entry-1",
                url=request.url,
                request=request,
                playlist_id="playlist-1",
                playlist_index=1,
                playlist_title="Trail Sounds",
                queue_position=0,
            )
        ]
    )
    connection.close()

    composition = composed(
        database=database,
        entry_point=child_probing_then_waiting,
    )
    # **The queue is stopped until it is started** (`UX-006`, `T-181`), so a composed test that
    # expects bytes to move has to press Start exactly as a user does. Called on the manager
    # rather than through the toolbar because the seam under test here is not the control.
    #
    # `ARC-009`'s probe-before-download is what this test is about, and Start is now what buys
    # **both** halves: since `T-215` composition holds the previous run's rows until the queue is
    # started, so this entry is read and *then* downloaded on the far side of this call. *(This
    # comment said the probe ran either way, the gate being blind to it. Running it either way is
    # what turned an offline launch into a wall of failures.)*
    composition.manager.start_queue()

    assert spin(lambda: shown_status(composition, "entry-1") is JobStatus.RUNNING, timeout=60), (
        "the playlist entry left queued on disk never reached its download"
    )
    stored = composition.store.get("entry-1")
    assert stored is not None
    assert stored.title == "A video that exists", (
        "startup downloaded a flat playlist entry without first probing it; the live add-dialog "
        "path honours ARC-009, but the durable restart path still admits QUEUED as DOWNLOAD"
    )


def test_an_offline_launch_leaves_the_durable_queue_held(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """**`T-215`.** A bad network moment at launch must not rewrite the queue into failures.

    **Observed live before it was filed**: launched with unreachable URLs, every durably-`QUEUED`
    row became `Failed` within a second — queue stopped, user touching nothing. Startup admitted
    those rows as probe sessions; the stopped-queue gate exempted *every* probe; a failed probe
    fails the job. `REQ-018` then retried the network error and failed it again. The user's
    standing queue is data they committed, and this rewrote it into work they must retry row by
    row.

    The proof is in three parts, because a bare "nothing happened yet" assertion would pass on a
    slow runner for entirely the wrong reason:

    1. **The mechanism, and no clock is involved in it** — `compose()` admitted synchronously, so
       the moment it returns the row is either started or not started at all. The manager must be
       holding **nothing**: `active_job_ids()` empty, which covers running, reserved *and*
       waiting. Asked that way deliberately — the first draft of this test asked `_sessions`
       alone and **passed on the unfixed tree**, because the startup probe was still a
       reservation at that instant. A reservation is a start whose transition has not landed
       yet, which is started, not held.
    2. **What the user sees** — the row still reads `QUEUED`, which `UX-006` shows as `Held`.
    3. **A positive control** — pressing Start reaches `FAILED` carrying the extractor's own text.
       Deferral is not suppression (`T-215`'s own criterion), and a test that could not observe
       the failure at all would be no evidence that it had been deferred.
    """
    database = tmp_path / "offline-launch.sqlite3"
    connection = db.connect(database)
    repository = JobRepository(connection)
    request = DownloadRequest(
        url="https://example.invalid/queued-last-session",
        output_directory=str(tmp_path / "downloads"),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )
    repository.append([Job(id="held-1", url=request.url, request=request, queue_position=0)])
    connection.close()

    # The offline shape: every session kind fails with the timeout a launch on a train produces.
    composition = composed(database=database, entry_point=child_failing_to_extract)
    manager = composition.manager

    assert not manager.active_job_ids(), (
        f"the manager took on {manager.active_job_ids()} at launch with the queue stopped: the "
        "startup probe ran unattended, which is the network moment T-215 is about"
    )
    assert spin(lambda: shown_status(composition, "held-1") is not None, timeout=30), (
        "the queue view never showed the row a previous run left behind"
    )
    assert shown_status(composition, "held-1") is JobStatus.QUEUED, (
        f"the held row reads {shown_status(composition, 'held-1')}, not Held (UX-006)"
    )
    stored = composition.store.get("held-1")
    assert stored is not None and stored.error_message is None, (
        "a row that has never been checked is carrying a failure message, so it claims knowledge "
        "it does not have"
    )

    # **The positive control.** Start is what the user presses; the probe runs then, fails then,
    # and says why — the same failure, moved to the moment it was actually attempted.
    manager.start_queue()
    assert spin(lambda: shown_status(composition, "held-1") is JobStatus.FAILED, timeout=60), (
        "the deferred row never failed once the queue was started, so the fix suppressed the "
        "failure rather than deferring it"
    )
    failed = composition.store.get("held-1")
    assert failed is not None and failed.error_message is not None
    assert "urlopen error" in failed.error_message, (
        f"the extractor's own message did not survive the deferral: {failed.error_message!r}"
    )


def test_a_held_row_still_probes_and_downloads_once_the_queue_starts(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """**`T-215`'s other half**: deferring must not strand a row that can never start.

    The risk the deferral creates is an unprobed row nobody probes — held at launch, and then
    still held after Start because the drain carried it as a download, or not at all. So this
    drives the same seam with a child that answers: held while stopped, and once started it is
    **probed and then downloaded**, with the title from the probe proving `ARC-009`'s order
    survived the parking.
    """
    database = tmp_path / "held-then-started.sqlite3"
    connection = db.connect(database)
    repository = JobRepository(connection)
    request = DownloadRequest(
        url="https://example.invalid/held-then-started",
        output_directory=str(tmp_path / "downloads"),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )
    repository.append([Job(id="wake-1", url=request.url, request=request, queue_position=0)])
    connection.close()

    composition = composed(database=database, entry_point=child_probing_then_waiting)
    manager = composition.manager

    assert not manager.active_job_ids(), (
        "the row did not wait for Start, so what follows proves nothing about waking it"
    )

    manager.start_queue()
    assert spin(lambda: shown_status(composition, "wake-1") is JobStatus.RUNNING, timeout=60), (
        "a row held at launch never reached its download after Start: the deferral stranded it"
    )
    stored = composition.store.get("wake-1")
    assert stored is not None and stored.title == "A video that exists", (
        "the held row was downloaded without being probed first; the deferral must park the "
        "probe, not replace it with a download (ARC-009)"
    )


def test_a_stopped_queue_still_reads_a_url_the_user_pastes(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """**The exemption `T-215` narrowed down to, guarded.** Staging is attended reading.

    `_gate_blocks` stops the queue's own rows and exempts a *staged* probe, and `UX-006` makes
    that exemption load-bearing rather than considerate: the queue is stopped at **every** launch,
    so a gate over staged probes leaves a first-run window unable to read anything pasted into it.

    **Nothing tested it.** Every add-dialog test builds its manager through a fixture that calls
    `start_queue()`, so the whole suite runs with the queue *running* and the launch state — which
    is the only state a first paste ever happens in — was covered nowhere. Measured, not assumed:
    with `_gate_blocks` mutated to gate staged probes too, `tests/ui/test_add_dialog.py` passed
    142 tests. This is the test that fails.

    Driven at the manager, which is the seam the rule lives on; the dialog's own use of it is
    `tests/ui/test_add_dialog.py`'s subject.
    """
    composition = composed(entry_point=child_probing_then_waiting)
    manager = composition.manager
    assert not manager.is_running, (
        "the composed queue is running at launch, so this cannot prove what a stopped one reads"
    )

    read: list[str] = []
    manager.media_probed.connect(lambda job_id, _media: read.append(job_id))
    staged = manager.stage(
        DownloadRequest(
            url="https://example.invalid/just-pasted",
            output_directory=str(tmp_path / "downloads"),
            format_selector="best",
            output_template="%(title)s.%(ext)s",
        )
    )

    assert spin(lambda: staged in read, timeout=60), (
        "a URL pasted into a first-run window was never read: the pause gate caught a staged "
        "probe, and the add dialog can only ever offer what it has read (UX-003)"
    )


def test_a_chosen_download_folder_survives_a_restart_and_is_where_a_job_goes(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """**`T-146`'s criterion, asserted against a real job** rather than against the stored value.

    *"A chosen directory survives a restart and is what a new job actually uses"* — and the second
    half is the one that fails quietly. `T-075` is the shape it fails in: a control that changes
    what is stored and not what runs. So this composes an application whose settings file already
    names a folder — which is what a restart *is*, the file being the only thing that crosses one
    — and then reads the folder off a job the composed application built for itself.

    Not passed as `output_directory=`: that argument is how the tests redirect downloads away from
    a real home directory, and it outranks the stored setting deliberately. A test that passed it
    would be asserting on its own argument.
    """
    chosen = tmp_path / "Trail recordings"
    chosen.mkdir()
    settings_file = tmp_path / "settings.toml"
    assert (
        core_settings.save(
            core_settings.with_download_directory(core_settings.Settings(), chosen), settings_file
        )
        is None
    )

    composition = composed(
        settings_file=settings_file, output_directory=None, entry_point=child_probing_then_waiting
    )

    assert composition.output_directory == chosen, (
        f"the composed application downloads into {composition.output_directory}, not the folder "
        "the settings file names"
    )
    dialog = composition.window.open_add_dialog()
    assert dialog is not None
    try:
        type_urls(dialog, "https://composed.invalid/where-does-this-go")
        dialog.resolve()
        assert spin(lambda: bool(dialog.rows) and dialog.rows[0].committable, timeout=60), (
            f"the URL never resolved: {dialog.status_text()}"
        )
        # Through the dialog's own single request builder (`T-075`, `UX-004`) — the one every
        # committed job goes through, rather than a second construction this test invented.
        built = dialog._request_for(dialog.rows[0])
        assert Path(built.output_directory) == chosen, (
            f"a job this application built writes to {built.output_directory}, not the chosen "
            f"folder {chosen}. The setting is stored and does not run — T-075's shape"
        )
    finally:
        dialog.close()
        QApplication.processEvents()


def test_a_setting_that_could_not_be_saved_says_so(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """**`T146-R2`.** A change that cannot be persisted must not look like one that was.

    `save()` has returned its failure rather than raising since `T109-R9`, and `T-146`'s three
    settings callbacks dropped it — so on a full disk or a read-only profile directory the user
    got a setting that visibly took effect and was gone at the next launch. *"A chosen directory
    survives a restart"* is the criterion, and a silent write failure is exactly where it does not.

    **Driven through a real control on the composed application**: the Settings screen's spinner,
    whose handler is composition's own `choose_concurrency`. *(The toolbar's, until `UX-013` moved
    the limit into that screen.)* All three callbacks route through the same
    `remember` helper, so this exercises the shared mechanism rather than one caller's copy of it —
    and concurrency is the one of the three with no global side effect, so it can be driven without
    restyling the `QApplication` every other test in this session shares.

    The write is made to fail by putting a **file where the settings file's parent folder should
    be**, after composition has read it: `save()`'s first act is to `mkdir` that parent, and a
    `mkdir` blocked by a file raises on every platform. *(This used a directory in the target's own
    place and relied on `os.replace` refusing it — true, but Windows behaviour I cannot run here,
    which is the class of claim `T146-R3` was. `mkdir` against a file is bedrock on both.)* No
    permission bits either, so it runs as root as well.
    """
    settings_file = tmp_path / "config" / "settings.toml"
    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)
    spinner = concurrency_control(composition)

    # After composition has read it, so startup is ordinary and only the *write* fails.
    shutil.rmtree(settings_file.parent, ignore_errors=True)
    settings_file.parent.write_text("a file where the folder should be", encoding="utf-8")

    spinner.setValue(spinner.value() + 1)
    QApplication.processEvents()

    assert composition.manager.concurrency == spinner.value(), (
        "the change did not apply, so this proves nothing about reporting a failed save"
    )
    said = composition.window.statusBar().currentMessage()
    assert "could not be saved" in said, (
        f"the status bar says {said!r}. A setting that applied but could not be written is one "
        "the user will lose at the next launch without ever being told"
    )


def test_the_theme_the_file_names_is_the_one_composition_reports(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """`REQ-023`, `T-146`: the stored palette reaches the running application through `run()`.

    **`compose()` carries the name rather than applying it**, and that is deliberate: restyling
    the `QApplication` here would restyle the one every other test in this session shares, which
    is the rule the `theme.apply` comment in `run()` states. So the assertion is that composition
    *reports* what the file said, and `tests/unit/test_theme.py` owns what `apply` then does with
    it.
    """
    settings_file = tmp_path / "settings.toml"
    assert (
        core_settings.save(
            core_settings.with_theme(core_settings.Settings(), "dark"), settings_file
        )
        is None
    )

    composition = composed(settings_file=settings_file)

    assert composition.theme == "dark", (
        f"the settings file asks for dark and composition reports {composition.theme!r}"
    )
    assert composition.theme in ui_theme.THEMES, "composition reported a theme with no palette"


def connection_count(sender: QObject, signal_name: str) -> int:
    """How many slots are connected to `signal_name` on `sender`.

    Asked of Qt rather than of our own bookkeeping (`docs/project/TESTING.md` §13): a count this
    code kept would agree with this code. `receivers()` wants the `SIGNAL()`-encoded signature,
    which the meta-object supplies.
    """
    meta = sender.metaObject()
    for index in range(meta.methodCount()):
        method = meta.method(index)
        if (
            method.methodType() == QMetaMethod.MethodType.Signal
            and bytes(method.name().data()).decode("ascii") == signal_name
        ):
            signature = bytes(method.methodSignature().data()).decode("ascii")
            return int(sender.receivers("2" + signature))
    raise LookupError(f"{sender} has no signal named {signal_name!r}")


def type_urls(dialog: Any, text: str) -> None:
    dialog._urls.setPlainText(text)


# --- 1. the assembled path (`REQ-001`, `REQ-012`) ---------------------------------------------


def test_pasting_a_url_into_the_assembled_application_reaches_the_database(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """`T-036`'s first acceptance criterion, and the failure the task was filed for.

    Every component of this path had passing tests while `app.py` built a window with no manager,
    no job store and no output directory — so File → Add URLs… was disabled and none of it was
    reachable. This drives the *composed* application: open the real dialog from the real window,
    type, add, and read the row back out of SQLite through a connection the application does not
    own.
    """
    composition = composed(entry_point=child_probing_then_waiting)
    assert composition.window.can_add_urls, (
        "the window was built without everything the dialog needs; that is the defect T-036 "
        "exists to prevent"
    )

    dialog = composition.window.open_add_dialog()
    type_urls(dialog, "https://composed.invalid/one\nhttps://composed.invalid/two")
    # `UX-003`: both lines are read before either can be queued, so this waits on the rows before
    # committing. The previous version pasted and added in one breath, which was the whole defect
    # `T-118` is about — a URL entering the queue nobody had looked at.
    dialog.resolve()
    assert spin(
        lambda: len(dialog.rows) == 2 and all(row.committable for row in dialog.rows), timeout=60
    ), "the pasted URLs never resolved"
    dialog.add_to_queue()
    assert spin(lambda: len(dialog.queued_job_ids) == 2, timeout=30), "the paste never persisted"

    # Read through a *different* connection: the point is that the rows are on disk, not that the
    # application remembers writing them.
    reader = sqlite3.connect(tmp_path / "queue.db")
    try:
        urls = [row[0] for row in reader.execute("SELECT url FROM jobs ORDER BY queue_position")]
    finally:
        reader.close()
    assert urls == ["https://composed.invalid/one", "https://composed.invalid/two"]


def test_the_composed_application_downloads_a_file_and_shows_it_finished(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """Probe, queue, download, complete — through the assembled graph and nothing else.

    The progress view appears because the manager moved the job, not because a test built one:
    `T-036` connects `job_changed` to the window, and that connection is what makes the engine
    visible to a person at all.
    """
    composition = composed(entry_point=child_probing_then_succeeding)
    # **The queue is stopped until it is started** (`UX-006`, `T-181`), so a composed test that
    # expects bytes to move has to press Start exactly as a user does. Called on the manager
    # rather than through the toolbar because the seam under test here is not the control.
    composition.manager.start_queue()
    dialog = composition.window.open_add_dialog()
    type_urls(dialog, "https://composed.invalid/movie")
    dialog.resolve()

    assert spin(lambda: bool(dialog.rows) and dialog.rows[0].state is RowState.READY, timeout=60), (
        "the URL never resolved"
    )
    media = dialog.rows[0].media
    assert isinstance(media, MediaInfo) and media.title == "A video that exists"
    # **Nothing is in the queue yet, and that is the corrected behaviour** (`T118-R1`, `UX-005`).
    # Reading a URL is a staging probe with no queue row. The window used to latch its detail pane
    # onto the transient probe id and sit on it — the download completed and the pane still said
    # "ready", because the id it watched was never the one that ran. With no pane, the equivalent
    # claim is that the *queue* has nothing in it, which is the surface a user would be misled by.
    queue = composition.window.queue_view
    assert queue is not None and queue.model.job_ids() == (), (
        f"the queue is showing {queue.model.job_ids() if queue else '?'} for a URL nobody has "
        "added yet"
    )

    # The probe's *session* outlives its result: the manager releases it on a later tick. Adding
    # before then is refused by the pool of one, which the dialog reports rather than raises.
    assert spin(lambda: composition.manager.is_idle, timeout=60), "the probe session never ended"
    dialog.add_to_queue()
    assert "did not start" not in dialog.status_text(), dialog.status_text()
    # **Waited for, not read straight after `add_to_queue()`.** Adding goes through the writer
    # thread, so the ids arrive on a later turn of the event loop; indexing immediately raises
    # `IndexError` from a line that looks like bookkeeping.
    assert spin(lambda: bool(dialog.queued_job_ids), timeout=60), (
        f"nothing was ever queued: {dialog.status_text()}"
    )
    job_id = dialog.queued_job_ids[0]
    assert spin(lambda: shown_status(composition, job_id) is not None, timeout=60), (
        "the window never showed the job the manager was working on"
    )
    # **Waited on the view, not on the store**, and the difference is `T-013`'s ordering rather
    # than a detail. The writer thread commits the row and *then* signals the GUI thread, so
    # `store.get()` answers `COMPLETED` from disk while `job_changed` is still queued. The
    # database leading the UI is exactly the guarantee; a test that polled the store would be
    # asserting on the window in the gap between the two, and this one did.
    assert spin(lambda: shown_status(composition, job_id) is JobStatus.COMPLETED, timeout=60), (
        f"the download never completed; the row says {shown_status(composition, job_id)}"
    )

    job = composition.store.get(job_id)
    assert job is not None and job.output_path is not None
    assert Path(job.output_path).exists(), "the file the queue claims to have downloaded is absent"

    # **The finished row is still in the Queue tab** (`UX-005` §8), which is what makes that tab
    # answer "did it work", and it offers the two file verbs rather than a Cancel. The forbidden
    # half is `tests/ui/test_row_verbs.py`'s; this is the assembled application agreeing with it.
    queue = composition.window.queue_view
    assert queue is not None
    assert job_id in queue.model.job_ids(), (
        "a completed download left the Queue tab before anyone cleared finished jobs"
    )
    assert set(queue.verbs_of(job_id)) == {Verb.OPEN, Verb.REVEAL}, (
        f"a finished row offers {[v.value for v in queue.verbs_of(job_id)]}"
    )


# --- 2. the wiring itself ---------------------------------------------------------------------


def test_the_manager_holds_the_store_composition_built(
    composed: Callable[..., application.Composition],
) -> None:
    """Asserted by identity, so a second store cannot quietly service a second queue.

    `T-036`'s criterion is that *no component is constructed twice*. Two stores over one database
    would each hold their own in-flight revisions, and `ARC-005`'s ordering guarantee is a
    property of there being one writer — not of there being one writer per object.
    """
    composition = composed()

    assert composition.manager._repository is composition.store
    assert composition.window._manager is composition.manager
    assert composition.window._jobs is composition.store
    assert composition.window._job_reader is composition.store


def test_every_manager_signal_the_ui_needs_has_exactly_one_connection(
    composed: Callable[..., application.Composition],
) -> None:
    """A signal connected twice is how one queued job becomes two of everything downstream.

    Counted through Qt's own `receivers()`, not through bookkeeping this code keeps, because
    bookkeeping this code keeps would agree with this code (`docs/project/TESTING.md` §13).
    """
    composition = composed()
    manager = composition.manager

    # **One, and it is named** (`UX-005`, `T-124`). It was two: composition also connected
    # `on_job_changed` to claim the detail pane for the first watchable transition (`T-079`). The
    # pane is gone, so that listener is gone with it, and the queue table's model — which keeps
    # the rows current — is the only one left.
    #
    # **The number is written down rather than counted**, which is the whole point: this test
    # exists to fail when a listener appears that nobody meant, and a count derived from the
    # application would agree with the application by construction (`docs/project/TESTING.md` §13).
    # It has gone one → two → one, and each move was a decision recorded here.
    assert connection_count(manager, "job_changed") == 1, (
        "job_changed should have exactly the queue model's listener now that the detail pane is "
        "gone; a second is how one queued job becomes two of everything downstream"
    )
    # The queue model is the only thing listening to progress. It was zero before `T-079` and
    # briefly shared the signal with a detail view; a table that draws progress is the consumer
    # `T-017`'s repaint budget is about.
    assert connection_count(manager, "progress") == 1, (
        "the queue model should be the only progress listener"
    )
    for name in ("job_removed", "queue_reordered"):
        assert connection_count(manager, name) == 1, (
            f"{name} should have exactly the queue UI listener that reflects the durable change"
        )
    # **Two, and both are named** (`T181-R1`). The run control follows the gate so the toolbar
    # cannot disagree with the queue, and the queue model follows it so a waiting row can read
    # `Held` — two consumers of one fact, answering different questions. A third would mean
    # something else had started deciding what the gate means.
    assert connection_count(manager, "queue_running") == 2, (
        "queue_running should have the run control and the queue model, and nothing else"
    )
    # **One, and it is named.** The queue model rebuilds its rows. This was **two** until `T-170`:
    # the History view re-read as well, because clear-finished was the moment history stopped
    # agreeing with the queue and became the only record of what had been downloaded. That view was
    # removed, and then the ledger behind it was withdrawn outright (`REQ-020`, 2026-08-06), so
    # there is nothing left to re-read — one listener is the whole answer (`T-176`).
    assert connection_count(manager, "queue_cleared") == 1, (
        "queue_cleared should have exactly the queue model's listener"
    )
    # **Nothing at all**, and now for a simpler reason than when this was written. A completion
    # used to write a ledger row in the same transaction (`T050-R1`) that no surface showed; the
    # row and the ledger are both gone, so a completion writes only the job (`T-176`).
    assert connection_count(manager, "job_succeeded") == 0, (
        "job_succeeded gained a listener; a completion updates the job the queue is already "
        "watching, and nothing else records it (REQ-020 withdrawn)"
    )

    # **One each, and it is the window's** (`T-315`). These were **zero** until a queue row's
    # *Choose specific formats…* had to re-read its URL: a queued `Job` does not carry its format
    # list, so the window stages a probe and listens for the answer on the same two signals every
    # other probe uses. It is keyed on the probe's own id and ignores results it did not ask for,
    # which `test_a_probe_this_window_did_not_start_is_ignored` asserts from the other side.
    for name in ("media_probed", "job_failed"):
        assert connection_count(manager, name) == 1, (
            f"{name} should have exactly the window's re-read listener before the dialog opens"
        )

    dialog = composition.window.open_add_dialog()
    # The dialog adds its own four. Named individually rather than counted in bulk, so a signal
    # gaining a second listener is reported as itself. `job_changed` is **two** here — the queue
    # model's and the dialog's — where it was three before `UX-005` removed the detail pane's.
    #
    # `media_probed` and `job_failed` are **two** for the same shape of reason: the window's
    # re-read listener above, and the dialog's own (`T-315`). Both stage their own probes and
    # both filter on the id they were given, so neither acts on the other's result.
    for name, expected in (
        ("media_probed", 2),
        ("job_failed", 2),
        ("persistence_failed", 1),
        ("start_rejected", 1),
        ("job_changed", 2),
    ):
        assert connection_count(manager, name) == expected, (
            f"{name} has {connection_count(manager, name)} connections, expected {expected}"
        )
    dialog.close()


# **Three tests about the detail pane were removed here** (`UX-005`, `T-124`).
#
# `test_replacing_the_watched_job_leaves_no_second_listener`,
# `test_watching_the_same_job_twice_does_not_rebuild_the_view` and
# `test_a_second_job_starting_does_not_take_the_detail_pane_from_the_first` all drove
# `window.watch()`, which no longer exists: the row carries progress and state, and selecting one
# opens nothing.
#
# **The first of those was the only test of `JobProgressView.detach` anywhere**, and `UX-005`
# defers what becomes of that widget rather than deciding it — so its guarantee moved to
# `tests/ui/test_job_detail.py::test_a_detached_view_stops_answering_the_manager` *before* this
# deletion, and was mutation-checked there. Deleting it here without that would have turned a
# deferral into a silent deletion.

# --- 3. the environment (`REQ-024`) -----------------------------------------------------------


def test_startup_states_what_this_installation_cannot_do(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """`REQ-024`: report the ffmpeg state and name what will not work without it.

    Driven with an override that does not exist, because that is the case with something to say.
    A missing ffmpeg disables features; it does not stop the application, and the window has to
    say so where a user will see it rather than in a log they will not read.
    """
    composition = composed(ffmpeg_override=tmp_path / "no-such-ffmpeg")

    assert not composition.ffmpeg.available
    summary = composition.window.environment_text()
    assert "ffmpeg was not found" in summary, f"the window says {summary!r}"
    assert "Unavailable:" in summary, (
        "the report named no features, so a user learns that something is wrong and not what"
    )


def an_executable_ffmpeg(directory: Path, name: str = "ffmpeg") -> Path:
    """A file the platform's own rules call executable (`T-062`, `T199-R4`).

    **What "executable" means is the platform's answer, not a mode bit.** A `#!/bin/sh` script with
    `chmod 0755` is executable on POSIX and invisible to `shutil.which` on Windows, which decides
    by `PATHEXT` — so a test writing one fails there and only there. `find_ffmpeg` uses
    `shutil.which` precisely so the platform's rule applies (`T035-R2`), and a test exercising it
    has to honour the same rule.

    **A helper because writing it out twice is what went wrong.** The comment above lived inside
    one test; `T-199` added another three tests below it and wrote the POSIX-only shape anyway,
    which `T199-R4` caught as a deterministic Windows failure. A reader cannot forget a helper.
    """
    # `os.name`, not `sys.platform`: mypy narrows the latter under `--platform win32` until
    # everything after it is unreachable, which is a gate failure rather than a portability one.
    if os.name == "nt":
        fake = directory / f"{name}.bat"
        fake.write_text("@echo off\r\nexit /b 0\r\n")
        return fake
    fake = directory / name
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(0o755)
    return fake


def test_a_usable_ffmpeg_is_reported_as_usable_and_reaches_the_manager(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """The path is *passed on*, not merely found — the defect class this project met five times.

    `docs/project/STATUS.md` records it: the resolved yt-dlp version never left the worker, ffmpeg
    was located and never passed to the library. Locating it here and dropping it would look correct
    and produce no error.
    """
    fake = an_executable_ffmpeg(tmp_path)
    composition = composed(ffmpeg_override=fake)

    assert composition.ffmpeg.available
    assert "all post-processing features are available" in composition.window.environment_text()
    assert composition.manager._ffmpeg_override == composition.ffmpeg.path, (
        "ffmpeg was located and then not handed to the manager, so no worker would ever see it"
    )


def test_the_settings_screen_composition_opens_can_actually_update_ytdlp(
    composed: Callable[..., application.Composition],
) -> None:
    """`T-198`: the screen opened by the real application has a route behind both actions.

    **This is the `T195-R4` shape, deliberately.** That finding was a test asserting the *store*
    and submitted as proof of the *wiring*, while the wiring was broken exactly as the review
    said. A `SettingsDialog` built by hand always has whatever callbacks the test passes it; only
    the screen `compose()` opens can say whether composition passed any.
    """
    composition = composed()

    screen = composition.window.open_settings()
    assert screen is not None

    update = screen.findChild(QPushButton, YTDLP_UPDATE_NAME)
    assert update is not None, "the composed settings screen has no yt-dlp update control"
    assert update.isEnabled(), "composition opened the screen with nothing behind the update"
    service = composition.window._ytdlp
    assert isinstance(service, QuietYtdlp)
    assert service.asked == ["refresh"], (
        "opening the screen did not ask which yt-dlp is in use, so it would show nothing"
    )


def test_a_reported_resolution_reaches_the_open_settings_screen(
    composed: Callable[..., application.Composition],
) -> None:
    """The service answers on a signal; the window must carry it to whichever screen is open.

    Driven by emitting on the real service rather than by calling the window's slot, because what
    is being asserted is that composition *connected* it — a slot that exists and is wired to
    nothing passes every test that calls it directly.
    """
    composition = composed()
    screen = composition.window.open_settings()
    assert screen is not None
    service = composition.window._ytdlp
    assert service is not None, "composition built no yt-dlp service"

    service.reported.emit(
        Resolution(version="2026.9.1", source="user-managed copy (OPS-002)", rejected=())
    )

    shown = screen.findChild(QLabel, YTDLP_VERSION_NAME)
    assert shown is not None
    assert "2026.9.1" in shown.text(), "a reported version never reached the open screen"
    revert = screen.findChild(QPushButton, YTDLP_REVERT_NAME)
    assert revert is not None and revert.isEnabled(), (
        "the screen was told a user copy is in use and still offers no way back"
    )


def test_the_updater_writes_where_the_manager_tells_workers_to_look(
    composed: Callable[..., application.Composition],
) -> None:
    """**The named worst outcome, guarded** (`T-198`).

    An update that lands somewhere the worker does not read reports a new version and changes
    nothing about the download that follows — it looks like it worked. Both sides used to reach
    `user_ytdlp_directory()` on their own, which is agreement by coincidence: two defaults that
    must match are two places to drift, and nothing would have failed the day one moved.

    Composition now names the directory once and hands it to both, and this is the assertion that
    keeps it that way. The real service is used here rather than `QuietYtdlp`, because what is
    being compared is the directory composition chose — and the stub deliberately carries a
    different one.
    """
    from tracks_and_trails.downloader.environment import user_ytdlp_directory

    composition = composed(ytdlp_service=None)
    service = composition.ytdlp

    assert service is composition.window._ytdlp, "the window was handed a different service"
    assert service.directory == composition.manager._user_ytdlp_directory, (
        "an update would be installed where no worker resolves it"
    )
    assert service.directory == user_ytdlp_directory()


def test_a_start_during_an_update_spawns_nothing_until_the_update_has_finished(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**`T198-R3`, at the seam the finding is about: the composed manager and service.**

    An install replaces the yt-dlp package tree a worker imports from, and on POSIX that
    replacement succeeds by design — a worker already inside `yt_dlp` resolves its *later* lazy
    imports, extractors included, from whatever now sits at that path. So the whole operation has
    to exclude worker starts, not merely begin with a question about them.

    The previous correction asked `workers_active()` once on the GUI thread and then submitted
    the real work to a pool, leaving seconds in which the GUI stayed live. The reviewer
    reproduced exactly that: the predicate went from false to true between the guard and the
    work, and the install proceeded regardless. **Here the press is the user's own Start**, made
    while the install is provably mid-flight, and the assertion is that no child is spawned until
    it ends.

    **Deterministic rather than timed.** The install blocks on an event this test owns, so the
    window it asserts inside is one the test opens and closes rather than one it hopes to catch;
    the negative is then given three seconds, which is many times what an unheld queue needs to
    spawn — the same shape `test_an_offline_launch_leaves_the_durable_queue_held` uses.

    **Everything else is the production path**: composition's own service, composition's own
    manager, the real hold. Two substitutions, both offline: the wheel is not fetched — this is
    not about installing — and the version is not re-asked from a spawned child, because the
    child would import the tree this test never writes.
    """
    from tracks_and_trails.downloader import ytdlp_service as ytdlp_service_module
    from tracks_and_trails.downloader.ytdlp_update import Release

    database = tmp_path / "update-during-start.sqlite3"
    connection = db.connect(database)
    request = DownloadRequest(
        url="https://composed.invalid/queued-before-the-update",
        output_directory=str(tmp_path / "downloads"),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )
    JobRepository(connection).append(
        [Job(id="queued-1", url=request.url, request=request, queue_position=0)]
    )
    connection.close()

    release = Release(
        version="9000.1.1",
        url="https://files.invalid/yt_dlp-9000.1.1-py3-none-any.whl",
        digest="0" * 64,
        filename="yt_dlp-9000.1.1-py3-none-any.whl",
    )
    installing = threading.Event()
    let_it_finish = threading.Event()

    def install(directory: Path, *, release: Release, cancelled: Any) -> Release:
        # `cancelled` is required rather than defaulted (`T289-R21`): the composed service hands
        # every install the pool's own stop question, and a fake that quietly accepted `**kwargs`
        # would go on passing if that seam were removed.
        assert cancelled is not None, "the composed service ran an install it could not stop"
        installing.set()
        assert let_it_finish.wait(timeout=60.0), "the test never released the install"
        return release

    monkeypatch.setattr(ytdlp_service_module, "latest_release", lambda: release)
    monkeypatch.setattr(ytdlp_service_module, "install_latest", install)
    monkeypatch.setattr(
        ytdlp_service_module,
        "resolve_in_a_child",
        lambda directory, **_: Resolution(version="9000.1.1", source="user-managed copy (OPS-002)"),
    )

    composition = composed(
        database=database, entry_point=child_probing_then_waiting, ytdlp_service=None
    )
    manager = composition.manager
    reported: list[Any] = []
    problems: list[str] = []
    composition.ytdlp.reported.connect(reported.append)
    composition.ytdlp.failed.connect(problems.append)

    try:
        composition.ytdlp.install_latest_version()
        assert spin(installing.is_set, timeout=60), "the install never began"
        assert not problems, f"the install was refused on an idle queue: {problems}"
        # Read into a local for the reason `concurrency_control`'s callers do: mypy narrows a
        # property across asserts, so asserting the opposite later types the rest of this test
        # as unreachable and it stops being a gate.
        holding = manager.starts_are_held
        assert holding, (
            "the composed service is not holding the composed manager; an install is running "
            "against a queue that is free to spawn workers into the tree it is replacing"
        )

        # The press. Start on a stopped queue fills every free slot immediately — which is the
        # whole point of `start_queue` and exactly what must not happen here.
        manager.start_queue()

        assert not spin(lambda: bool(manager._sessions), timeout=3), (
            f"a worker ({sorted(manager._sessions)}) was spawned in the middle of a yt-dlp "
            "install; it would import extractors from a directory being replaced under it"
        )
        assert manager.active_job_ids() == ("queued-1",), (
            "the Start was dropped rather than parked, so the user's press is lost"
        )
    finally:
        let_it_finish.set()

    assert spin(lambda: bool(reported), timeout=60), f"the install never finished: {problems}"
    assert not problems, f"the install failed: {problems}"
    handed_back = manager.starts_are_held
    assert not handed_back, "the finished install kept the workers held"
    assert spin(lambda: shown_status(composition, "queued-1") is JobStatus.RUNNING, timeout=60), (
        "the download the update had parked never ran afterwards"
    )


# --- 4. shutdown (`T013-R2`, `T038-R2`, `ARC-005`) --------------------------------------------


def test_closing_the_window_with_a_download_running_stops_everything_in_order(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """The whole of `T-036`'s shutdown criterion, driven from the window's own close.

    Order matters and each step is asynchronous: the manager stops the worker and reaps its tree,
    the writer then finishes the transitions the manager queued on its way down, and only then is
    the database closed. Quitting earlier leaves an orphaned process or loses a row.
    """
    composition = composed(entry_point=child_probing_then_waiting)
    # **The queue is stopped until it is started** (`UX-006`, `T-181`), so a composed test that
    # expects bytes to move has to press Start exactly as a user does. Called on the manager
    # rather than through the toolbar because the seam under test here is not the control.
    composition.manager.start_queue()
    dialog = composition.window.open_add_dialog()
    type_urls(dialog, "https://composed.invalid/long")
    dialog.resolve()
    assert spin(lambda: bool(dialog.rows) and dialog.rows[0].state is RowState.READY, timeout=60)
    assert spin(lambda: composition.manager.is_idle, timeout=60), "the probe session never ended"
    dialog.add_to_queue()
    assert spin(lambda: composition.manager.active_job_ids() != (), timeout=60), (
        "no download was running, so this proves nothing about closing with one"
    )
    job_id = composition.manager.active_job_ids()[0]

    # Qt's default is to quit the instant the last window closes, which is step zero of the wrong
    # order: the worker is still alive and the database still open. Asserted structurally because
    # its absence has no in-process consequence — the process would simply be gone, and a test
    # cannot observe its own exit.
    assert composition.app.quitOnLastWindowClosed() is False, (
        "Qt will quit when the window closes, before the worker is stopped or the database "
        "is closed"
    )

    composition.window.close()

    assert composition.shutdown.begun, "closing the window did not begin the shutdown lifecycle"
    assert spin(lambda: composition.shutdown.finished, timeout=60), "shutdown never finished"
    assert composition.manager.is_idle
    assert not composition.writer.is_running, "the writer thread outlived the shutdown"

    # The database is closed, and closed *after* the writes: a fresh reader sees the cancellation.
    with pytest.raises(sqlite3.ProgrammingError):
        composition.connection.execute("SELECT 1")
    reader = db.connect(tmp_path / "queue.db")
    try:
        stored = JobRepository(reader).get(job_id)
    finally:
        reader.close()
    assert stored is not None
    assert stored.status is JobStatus.CANCELLED, (
        f"the job was left {stored.status.value} on disk; closing the window cancels what is "
        "running, and the writer finishes before the connection closes"
    )


def test_shutdown_is_idempotent_and_does_not_quit_on_an_ordinary_idle(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
) -> None:
    """`idle` is emitted whenever the last session is released, not only while shutting down.

    Closing the writer on an ordinary idle would end persistence while the application was still
    running — the queue would keep working and nothing would ever reach disk again.
    """
    composition = composed(entry_point=child_probing_then_succeeding)
    dialog = composition.window.open_add_dialog()
    type_urls(dialog, "https://composed.invalid/short")
    dialog.resolve()
    assert spin(lambda: bool(dialog.rows) and dialog.rows[0].state is RowState.READY, timeout=60)
    assert spin(lambda: composition.manager.is_idle, timeout=60), "the probe never finished"

    assert not composition.shutdown.finished, "an ordinary idle closed the writer"

    # **Asserted by writing, not by asking whether the thread is alive.** `close()` is
    # asynchronous, so `is_running` can still be true for a moment after an early close — a check
    # that samples it proves nothing, and a mutation closing the writer on every idle survived
    # exactly that check. What must still be true is that persistence *works*.
    second = composition.window.open_add_dialog()
    type_urls(second, "https://composed.invalid/after-idle")
    # `UX-003`: reading the URL is itself a write, so this waits for the row to resolve before
    # committing. That the row resolved at all is the persistence this test is about.
    second.resolve()
    assert spin(lambda: bool(second.rows) and second.rows[0].committable, timeout=60), (
        "the URL never resolved, so nothing could be queued for reasons other than the writer"
    )
    second.add_to_queue()
    assert spin(lambda: len(second.queued_job_ids) == 1, timeout=60), (
        "nothing could be queued after an ordinary idle; the writer was closed while the "
        "application was still running"
    )
    second.close()

    composition.shutdown.begin()
    composition.shutdown.begin()
    assert spin(lambda: composition.shutdown.finished, timeout=60)


# --- 5. cold start (`NFR-002`) ----------------------------------------------------------------


def test_cold_start_with_the_whole_graph_fits_the_budget(
    qapp: QApplication,
    tmp_path: Path,
    spin: Callable[..., bool],
    record_property: Callable[[str, object], None],
) -> None:
    """`NFR-002`: three seconds, measured with everything constructed.

    `T-007` measured an empty window at 0.178 s and said so; this measures the graph that window
    now hangs off — a migrated database, a writer thread, a manager, and the window itself.
    Recorded as a property rather than asserted alone, so the number is in the run's output when
    it starts drifting toward the budget rather than only when it crosses it.
    """
    started = time.perf_counter()
    composition = application.compose(
        qapp,
        database=tmp_path / "cold.db",
        output_directory=tmp_path / "downloads",
        geometry_file=tmp_path / "window.toml",
    )
    composition.window.show()
    qapp.processEvents()
    elapsed = time.perf_counter() - started

    record_property("cold_start_seconds", round(elapsed, 3))
    try:
        assert elapsed < 3.0, (
            f"cold start took {elapsed:.3f}s against NFR-002's 3s budget, with the full graph "
            "constructed"
        )
    finally:
        composition.window.close()
        assert spin(lambda: composition.shutdown.finished, timeout=60)


# --- 6. retry is composition's, and it is a write ---------------------------------------------


def test_retrying_a_failed_job_re_queues_it_and_starts_it_again(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
) -> None:
    """The seam `T-017` left open: the widget reports `retry_requested`, this performs it.

    `ui/` holds no writer (`ARCHITECTURE.md` §3), so a retry that the view performed itself would
    be the layering violation `T-005` fails the suite for. What it costs is that nothing retried
    anything until composition existed — which is exactly the shape of gap `T-036` was filed for.
    """
    composition = composed(entry_point=child_probing_then_failing)
    # **The queue is stopped until it is started** (`UX-006`, `T-181`), so a composed test that
    # expects bytes to move has to press Start exactly as a user does. Called on the manager
    # rather than through the toolbar because the seam under test here is not the control.
    composition.manager.start_queue()
    dialog = composition.window.open_add_dialog()
    type_urls(dialog, "https://composed.invalid/gone")
    # **The URL reads, and the *download* fails** (`UX-003`, `T118-R1`). This used to fail the
    # probe, which no longer produces anything to retry: an unreadable URL never becomes a queue
    # job. `REQ-018`'s retry has always been about a job that failed downloading.
    dialog.resolve()
    assert spin(lambda: bool(dialog.rows) and dialog.rows[0].committable, timeout=60), (
        "the URL never resolved, so it could never be added"
    )
    dialog.add_to_queue()

    # Waited on the view, per the module docstring: the row is `FAILED` on disk before the
    # manager announces it, and a retry control that exists only after the announcement cannot
    # be asserted on before it. Waiting on `is_idle` here would be worse still — it is true
    # before the download starts.
    # **Waited for, not read straight after `add_to_queue()`.** Adding goes through the writer
    # thread, so the ids arrive on a later turn of the event loop; indexing immediately raises
    # `IndexError` from a line that looks like bookkeeping.
    assert spin(lambda: bool(dialog.queued_job_ids), timeout=60), (
        f"nothing was ever queued: {dialog.status_text()}"
    )
    failed_id = dialog.queued_job_ids[0]
    assert spin(lambda: shown_status(composition, failed_id) is JobStatus.FAILED, timeout=60), (
        "the download never failed, so there is nothing to retry"
    )

    view = composition.window.queue_view
    assert view is not None
    assert Verb.RETRY in view.verbs_of(failed_id), (
        f"a network failure is retryable and the row does not offer it: "
        f"{[v.value for v in view.verbs_of(failed_id)]}"
    )
    failed = composition.store.get(failed_id)
    assert failed is not None and failed.status is JobStatus.FAILED
    transitions: list[str] = []
    composition.manager.job_changed.connect(lambda job_id, status: transitions.append(status))

    # **Through the row's own verb**, which is the route a user has since `UX-005`. Emitting the
    # signal directly would assert on composition's wiring while skipping the thing that reaches
    # it, and `T-124`'s whole risk is a second route that quietly does something else.
    view.trigger_verb(failed_id, Verb.RETRY)

    # **A retry that leaves an inert queued row is not a retry** (`T036-R1`). The previous version
    # of this test asserted only that the job left `FAILED`, and a comment here argued that
    # starting was not part of the promise. The reviewer measured what that argument costs: the
    # failed session had not been released yet, the pool of one refused the start, the refusal was
    # swallowed, and five seconds later nothing had happened — a queued row nobody was running, a
    # view still showing the old failure, and a Retry button that did nothing the second time.
    assert spin(lambda: "queued" in transitions, timeout=60), (
        f"the re-queue was never announced, so no widget could learn about it: {transitions}"
    )
    assert spin(lambda: any(s in transitions for s in ("probing", "running")), timeout=60), (
        f"the retry re-queued the job and never started it: {transitions}"
    )

    # The row stops showing the old failure, because the manager announced the transition. When
    # composition wrote it through the store instead, nothing did.
    assert spin(lambda: shown_status(composition, failed_id) is not JobStatus.FAILED, timeout=60), (
        "the queue row still shows the failure this retry replaced"
    )


# --- T-078: the limit changes through the control a person can reach ------------------------


def test_the_limit_changes_through_the_control_and_survives_a_restart(
    composed: Callable[..., application.Composition], tmp_path: Path
) -> None:
    """`T-078`, `ARC-007`: **driven through the widget, never the constructor.**

    The criterion exists because a pool whose limit is only a constructor argument satisfies every
    behavioural test and misses `REQ-013` entirely — that is what `P2PLAN-R3` reported. So this
    reaches the real `QSpinBox` by object name and sets a value, exactly as a person would, and
    asserts two separate things: the **running pool** changed, and the change is on **disk**.

    "Survives a restart" is asserted by composing a second application against the same settings
    file rather than by trusting `save()`. A second graph reading the value back is the only form
    of that claim which cannot pass against a write that never happened.
    """
    from tracks_and_trails.core import settings as app_settings

    settings_file = tmp_path / "settings.toml"
    first = composed(settings_file=settings_file)

    box = concurrency_control(first)
    assert box.value() == app_settings.CONCURRENCY_DEFAULT
    assert first.manager.concurrency == app_settings.CONCURRENCY_DEFAULT

    box.setValue(5)

    assert first.manager.concurrency == 5, (
        "the running pool did not change. A control that edits a file and not the pool is T-075's "
        "shape one setting over: the stored value and the running behaviour disagree"
    )
    assert app_settings.load(settings_file).settings.concurrency == 5, (
        "the choice never reached disk"
    )

    second = composed(
        database=tmp_path / "second.db",
        geometry_file=tmp_path / "second-window.toml",
        settings_file=settings_file,
    )
    assert second.manager.concurrency == 5, "a restart did not pick the chosen limit back up"
    assert concurrency_control(second).value() == 5, (
        "the control came back showing a different number from the pool it governs"
    )


def test_the_control_offers_exactly_the_range_the_settings_layer_allows(
    composed: Callable[..., application.Composition], tmp_path: Path
) -> None:
    """The widget's range is read from `core/settings.py`, not restated beside it.

    A spinbox with its own numbers would be a second opinion about `REQ-013`'s minimum and
    `ARC-007`'s ceiling. It bounds the *widget*; the bound that matters is on the value, which is
    why `settings.toml` is clamped independently and a hand-edited `0` still becomes 1.
    """
    from tracks_and_trails.core import settings as app_settings

    composition = composed(settings_file=tmp_path / "settings.toml")
    box = concurrency_control(composition)
    assert box.minimum() == app_settings.CONCURRENCY_MINIMUM
    assert box.maximum() == app_settings.CONCURRENCY_MAXIMUM


def test_lowering_the_limit_through_the_control_holds_new_work_without_stopping_old(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """`T078-R2`: lowering was **written down and not enforced**, and nothing could see it.

    Two mutations survived the committed suite, and they are the same gap from either end:

    - Composition applying increases but only *saving* decreases passed the entire 14-test file,
      because the one real-control test moves 3 → 5 and never down.
    - The scheduler starting waiting work while the live count was above the lowered limit passed
      every pool test, because the drain test has nothing waiting for it to wrongly start.

    So this lowers a **saturated** pool through the real `QSpinBox` with a fourth job accepted
    behind it, and asserts the three things that distinguish an enforced limit from a recorded
    one: the running work survives, the waiting work stays waiting while the pool is over the new
    limit, and it starts once the pool is under it.

    Jobs are submitted to the real store and started through the real manager rather than typed
    into the add dialog four times — the path under test is control → pool, and
    `test_the_limit_changes_through_the_control_and_survives_a_restart` already drives the
    control end-to-end. `_start_when_free` is reached directly because it is the only admission
    path into the waiting list: `start()` at saturation raises instead of queueing.
    """
    from datetime import UTC, datetime

    from tracks_and_trails.core import settings as app_settings
    from tracks_and_trails.core.models import Job

    settings_file = tmp_path / "settings.toml"
    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)
    # **The queue is stopped until it is started** (`UX-006`, `T-181`), so a composed test that
    # expects bytes to move has to press Start exactly as a user does. Called on the manager
    # rather than through the toolbar because the seam under test here is not the control.
    composition.manager.start_queue()
    manager = composition.manager
    assert manager.concurrency == 3, "this test needs the default limit to be the saturated one"

    saved: list[str | None] = []
    composition.store.submit(
        [
            Job(
                id=job_id,
                url=f"https://composed.invalid/{job_id}",
                request=DownloadRequest(
                    url=f"https://composed.invalid/{job_id}",
                    output_directory=str(tmp_path / "downloads"),
                    format_selector="best",
                    output_template="%(title)s.%(ext)s",
                ),
                created_at=datetime.now(UTC),
            )
            for job_id in ("job-1", "job-2", "job-3", "job-4")
        ],
        saved.append,
    )
    assert spin(lambda: bool(saved), timeout=60), "the queue rows were never written"
    assert saved == [None], f"submitting the queue failed: {saved}"

    for job_id in ("job-1", "job-2", "job-3"):
        manager.start(job_id)
    manager._start_when_free("job-4")
    assert spin(lambda: len(manager._occupant_ids()) == 3, timeout=60), (
        f"the pool never saturated: occupants {manager._occupant_ids()}"
    )
    assert manager._waiting == ["job-4"]

    box = concurrency_control(composition)
    box.setValue(1)

    assert manager.concurrency == 1, (
        "the running pool kept the old limit. A handler that applies increases and merely stores "
        "decreases leaves the file saying 1 and the pool running 3 — T-075's shape, one setting "
        "over, and invisible to any test that only ever raises the limit"
    )
    assert app_settings.load(settings_file).settings.concurrency == 1, (
        "the decrease never reached disk"
    )

    # The tick fills free slots too, so give it several before deciding nothing started.
    spin(lambda: False, timeout=0.5)
    assert manager._occupant_ids() == ("job-1", "job-2", "job-3"), (
        "lowering the limit through the control stopped work already in flight; UX-001 chose "
        "draining, and REQ-017's resume does not exist to make a partial file recoverable"
    )
    assert manager._waiting == ["job-4"], (
        "the waiting job started while three were live and the limit was 1. Lowering governs "
        "what starts next; a pool that fills slots it does not have has no limit at all"
    )

    for job_id in ("job-1", "job-2", "job-3"):
        manager.cancel(job_id)

    assert spin(lambda: manager._occupant_ids() == ("job-4",), timeout=60), (
        "the waiting job never became eligible once the pool drained below the new limit: "
        f"occupants {manager._occupant_ids()}, waiting {manager._waiting}"
    )


# --- T-079: the queue table in the assembled application --------------------------------------


def child_streaming_its_own_size(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """A download that reports a size derived from its job id, then finishes.

    Per-job sizes because three identical rows are what the defect looks like: a table routing
    every message into one row passes any check that merely counts rows or waits for progress.
    The manager writes the worker's total at the terminal transition, so the *worker* has to be
    the thing that differs — seeding the rows would be overwritten.
    """
    if kind is SessionKind.PROBE:
        from tracks_and_trails.core.models import MediaInfo

        queue.put(Probed(job_id=job_id, media=MediaInfo(url=request.url, title=f"Video {job_id}")))
        queue.put(WorkerFinished(job_id=job_id, exit_code=0))
        return

    total = 1024 * int(job_id.rsplit("-", 1)[1])
    output = Path(request.output_directory) / f"{job_id}.mp4"
    output.write_bytes(b"x" * total)
    for fraction in (0.5, 1.0):
        queue.put(
            Progress(
                job_id=job_id,
                stage=Stage.DOWNLOADING_VIDEO,
                downloaded_bytes=int(total * fraction),
                total_bytes=total,
            )
        )
        # Longer than one `REPAINT_INTERVAL_MS`, so each job is drawn at least once before it
        # ends. Faster than that and the terminal state drops the pending message undrawn, which
        # would make the live assertion below a measurement of the timer rather than the routing.
        time.sleep(0.15)
    queue.put(Succeeded(job_id=job_id, output_path=str(output), total_bytes=total))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))


#: `NFR-001`'s interaction budget, in seconds. One pass of the event loop longer than this is a
#: visible stall to somebody holding the mouse button down.
BUDGET: Final = 0.1

#: How long the latency above is sampled for, once three downloads are confirmed running.
#:
#: Long enough that every worker delivers many updates inside it — at ~50 a second each, this is
#: over a hundred per job — and short enough that the gate does not dominate the suite. It is not
#: a deadline: nothing is waited *for* here, the loop simply measures for this long.
SAMPLE_WINDOW: Final = 2.0

#: The file `child_streaming_until_released` watches for. Written by the test when it has finished
#: measuring, so the workers stop only after the sampling window closes.
RELEASE_MARKER: Final = "release-the-workers"

#: The three jobs `queue_three` writes. Named once because several tests assert over exactly this
#: set, and a gate that iterated a *subset* would report full concurrency having watched two.
THREE_JOBS: Final = ("job-1", "job-2", "job-3")


def statuses_of(composition: application.Composition) -> dict[str, str | None]:
    """What the store says about each of `THREE_JOBS`, for a failure message.

    A gate that says "three jobs never ran at once" and stops there sends the next reader to the
    manager; one that says two were `completed` and one `queued` sends them to the pool limit.
    """
    return {
        job_id: job.status.value if (job := composition.store.get(job_id)) is not None else None
        for job_id in THREE_JOBS
    }


def child_streaming_until_released(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """A download that streams progress **until the test says stop** (`P2EXIT-R2`).

    `child_streaming_its_own_size` sends two messages and exits, which is right for a routing
    test and wrong for a measurement: three workers that each live a third of a second may barely
    overlap, so a gate that wants to sample *while three downloads run* has no state to sample.
    This one holds the state open, so the sampling window is chosen by the test rather than by
    how fast three interpreters happen to start.

    The release signal is a file rather than an `Event` because the entry point is spawned: a file
    under the job's own output directory needs nothing shared across the process boundary.

    Sizes still differ per job (`child_streaming_its_own_size`'s reason): three identical streams
    are what a table routing every message into one row looks like from outside.
    """
    if kind is SessionKind.PROBE:
        from tracks_and_trails.core.models import MediaInfo

        queue.put(Probed(job_id=job_id, media=MediaInfo(url=request.url, title=f"Video {job_id}")))
        queue.put(WorkerFinished(job_id=job_id, exit_code=0))
        return

    total = 1024 * int(job_id.rsplit("-", 1)[1])
    release = Path(request.output_directory) / RELEASE_MARKER
    sent = 0
    while not release.exists():
        sent += 1
        queue.put(
            Progress(
                job_id=job_id,
                stage=Stage.DOWNLOADING_VIDEO,
                downloaded_bytes=min(total, sent * 64),
                total_bytes=total,
            )
        )
        # ~50 updates a second per worker, so three of them put a real, sustained load through
        # the same queue and table the criterion is about. Slower than this and the gate measures
        # an idle event loop with occasional work in it.
        time.sleep(0.02)

    output = Path(request.output_directory) / f"{job_id}.mp4"
    output.write_bytes(b"x" * total)
    queue.put(Succeeded(job_id=job_id, output_path=str(output), total_bytes=total))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))


#: A template the application does not ship, for tests that must tell a **carried** value from a
#: rebuilt one (`T195-R4`). The retarget regression started from the shipped template, so dropping
#: the carry-across produced the same string and left the assertion green.
CUSTOM_TEMPLATE = "%(uploader)s - %(title)s.%(ext)s"


def queue_three(
    composition: application.Composition,
    spin: Callable[..., bool],
    where: Path,
    template: str = "%(title)s.%(ext)s",
) -> None:
    """Put three real rows in the composed application's own database."""
    from datetime import UTC, datetime

    from tracks_and_trails.core.models import Job

    saved: list[str | None] = []
    composition.store.submit(
        [
            Job(
                id=job_id,
                url=f"https://composed.invalid/{job_id}",
                request=DownloadRequest(
                    url=f"https://composed.invalid/{job_id}",
                    output_directory=str(where),
                    format_selector="best",
                    output_template=template,
                ),
                created_at=datetime.now(UTC),
            )
            for job_id in ("job-1", "job-2", "job-3")
        ],
        saved.append,
    )
    assert spin(lambda: bool(saved), timeout=60), "the queue rows were never written"
    assert saved == [None], f"submitting the queue failed: {saved}"


def test_the_composed_run_control_changes_the_real_manager(
    composed: Callable[..., application.Composition],
) -> None:
    """`T-080`, `T-181`: prove the toolbar-to-manager seam instead of either component alone."""
    composition = composed()
    action = composition.window.run_action
    assert action is not None

    # **Both start stopped, and that is asserted rather than assumed** (`UX-006`). The window's
    # control and the manager's gate are two defaults that must agree; composition does no initial
    # sync, so if either flips the other is silently wrong from the first frame.
    stopped = composition.manager.is_running
    assert not stopped, "the composed manager was running before anybody pressed Start"
    assert not action.isChecked(), "the control claimed a running queue on a stopped one"

    # Read into locals: mypy narrows a property across asserts, so asserting the opposite
    # afterwards types the rest of the test as unreachable and stops it being a gate. The same
    # idiom `job_detail`'s `view.failure` uses.
    action.trigger()
    running = composition.manager.is_running
    assert running
    assert action.isChecked()
    assert action.text() == "&Stop", (
        "a running queue's control still offers Start, so its label names the state it is in "
        "rather than what pressing it does"
    )

    action.trigger()
    again = composition.manager.is_running
    assert not again
    assert not action.isChecked()
    assert action.text() == "&Start"


def test_the_composed_move_control_updates_the_store_and_the_table(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """`T-081`: the row's verb, composition, manager, writer, and queue view form one reorder path.

    Driven through the **row** since `T124-R3` removed the toolbar's *Move up*: `UX-005` §4 chose
    row verbs rather than a toolbar acting on a selection, because with two tabs that toolbar has
    to guess which list it means. Everything below the verb is the path this test is about and is
    unchanged — `trigger_verb` is the route a click takes.
    """
    composition = composed()
    queue_three(composition, spin, tmp_path / "downloads")
    table = composition.window.queue_view
    assert table is not None
    table.refresh()
    assert Verb.MOVE_UP in table.verbs_of("job-2"), (
        "the row offers no Move up, so this test would prove nothing about the reorder path"
    )

    table.trigger_verb("job-2", Verb.MOVE_UP)

    assert spin(
        lambda: (
            tuple(job.id for job in composition.store.all_jobs()) == ("job-2", "job-1", "job-3")
        ),
        timeout=60,
    ), "the composed move action never reached the durable queue"
    assert table.model.job_ids() == ("job-2", "job-1", "job-3"), (
        "the database was reordered but the composed queue table still shows the old order"
    )


def test_the_composed_remove_control_updates_the_store_and_the_table(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """`T-080`: a durable removal must disappear from the assembled queue view.

    Through the row's own *Remove* since `T124-R3` — see the reorder test above for why the
    toolbar action it used to drive is gone.
    """
    composition = composed()
    queue_three(composition, spin, tmp_path / "downloads")
    table = composition.window.queue_view
    assert table is not None
    table.refresh()
    assert Verb.REMOVE in table.verbs_of("job-2") or Verb.CANCEL in table.verbs_of("job-2"), (
        f"a queued row offers {table.verbs_of('job-2')}, none of which removes it"
    )

    table.trigger_verb("job-2", Verb.REMOVE)

    assert spin(lambda: composition.store.get("job-2") is None, timeout=60), (
        "the composed Remove action never reached the durable queue"
    )
    # **Wait on the UI too** — this file's own rule, which this test broke. The store answering
    # `None` and the view being told are two moments, and asserting the second immediately after
    # the first is the gap the module docstring is about. It passed until `T-115` gave startup
    # admission more event traffic to get through, and then failed only in a full run.
    assert spin(lambda: "job-2" not in table.model.job_ids(), timeout=60), (
        f"the row was deleted but the composed queue table still shows it: {table.model.job_ids()}"
    )


def test_the_composed_clear_control_updates_the_store_and_the_table(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """`T-081`: Clear finished reaches the manager and refreshes the assembled queue view."""
    composition = composed()
    queue_three(composition, spin, tmp_path / "downloads")
    job = composition.store.get("job-2")
    assert job is not None
    settled: list[str | None] = []
    composition.store.update(job.with_status(JobStatus.CANCELLED), settled.append)
    assert spin(lambda: bool(settled), timeout=60)
    assert settled == [None]

    table = composition.window.queue_view
    action = composition.window.clear_completed_action
    assert table is not None and action is not None
    table.refresh()
    assert "job-2" in table.model.job_ids()

    action.trigger()

    assert spin(lambda: composition.store.get("job-2") is None, timeout=60), (
        "the composed Clear finished action never reached the durable queue"
    )
    # Wait on the UI, for the reason above and in this file's module docstring.
    assert spin(lambda: "job-2" not in table.model.job_ids(), timeout=60), (
        f"the finished row was cleared but the composed queue table still shows it: "
        f"{table.model.job_ids()}"
    )


def test_three_concurrent_downloads_each_keep_their_own_row(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """**Phase 2's first exit criterion, through the assembled application** (`T-079`).

    Three real worker processes against the real pool of three, a real database, and the real
    window — the criterion is about what a user sees, and a widget test with a fake store cannot
    make that claim about the application.

    The assertion is that each row ends up describing *its own* job. Three identical rows is what
    a table with one shared progress field looks like, and it passes any check that counts rows.
    """
    composition = composed(entry_point=child_streaming_its_own_size)
    # **The queue is stopped until it is started** (`UX-006`, `T-181`), so a composed test that
    # expects bytes to move has to press Start exactly as a user does. Called on the manager
    # rather than through the toolbar because the seam under test here is not the control.
    composition.manager.start_queue()
    queue_three(composition, spin, tmp_path / "downloads")
    table = composition.window.queue_view
    assert table is not None, "composition did not give the window a queue table"

    for job_id in ("job-1", "job-2", "job-3"):
        composition.manager.start(job_id)

    # **Asserted while they are live.** Measured: a model routing every message into row 0 passes
    # every completion assertion below, because those read the durable row and the durable rows
    # really are per job. What each row has *drawn* is the only place the routing can be seen.
    assert spin(
        lambda: all(
            table.model.displayed_progress(job_id) is not None
            for job_id in ("job-1", "job-2", "job-3")
        ),
        timeout=60,
    ), "a row never drew progress of its own, so messages are not being routed per row"
    for job_id in ("job-1", "job-2", "job-3"):
        drawn = table.model.displayed_progress(job_id)
        assert drawn is not None and drawn.job_id == job_id, (
            f"{job_id}'s row is showing {drawn.job_id if drawn else None}'s message"
        )

    assert spin(
        lambda: all(
            (job := composition.store.get(job_id)) is not None and job.status is JobStatus.COMPLETED
            for job_id in ("job-1", "job-2", "job-3")
        ),
        timeout=60,
    ), "the three downloads did not all finish"
    table.refresh()

    assert table.model.job_ids() == ("job-1", "job-2", "job-3"), (
        f"the table holds {table.model.job_ids()}, not one row per queued job"
    )
    sizes = {
        job_id: table.model.text_at(job_id, SIZE_COLUMN) for job_id in ("job-1", "job-2", "job-3")
    }
    assert len(set(sizes.values())) == 3, (
        f"the three rows report the same size, so they are not independent: {sizes}"
    )
    for job_id in ("job-1", "job-2", "job-3"):
        assert table.model.text_at(job_id, PROGRESS_COLUMN) == "100%"


def test_the_interface_stays_inside_its_budget_while_three_downloads_run(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
    qapp: QApplication,
    record_property: Callable[[str, object], None],
) -> None:
    """The other half of the criterion: **interactive throughout**, measured (`NFR-001`).

    "The UI stays responsive" is not testable; "no pass of the event loop takes longer than
    `NFR-001`'s ~100 ms budget while three workers stream progress into a six-column table" is.

    This is the measurement `T-017`'s single-job budget test cannot make, because the cost that
    matters here is three streams arriving at once rather than one.

    ## The measurement needs a positive control (`P2EXIT-R2`)

    An earlier version recorded only the worst `processEvents()` pass and asserted only the
    latency. A reviewer's mutation deleting all three `manager.start()` calls **passed in 60.24
    s**: an idle event loop is very fast, so the gate was satisfied by the absence of the thing it
    was named for. Three separate controls now stand between that and a pass:

    - **`active_job_ids` immediately after the starts** catches a start that never happened, and
      catches it *synchronously*: `start()` reserves the job before the writer thread runs, so the
      deleted-starts mutation now fails in milliseconds instead of after a minute.
    - **Every job seen `RUNNING` at one moment** catches three workers that took turns rather than
      overlapping.
    - **Every job advancing its own update count inside the sampling window** catches a
      measurement taken while the queue was quiet.

    The workers are held open by `child_streaming_until_released` rather than allowed to finish,
    so the window is chosen here instead of by three interpreters' start-up times — and then
    released, because a criterion about three downloads running has to end with three downloads
    that ran.
    """
    downloads = tmp_path / "downloads"
    composition = composed(entry_point=child_streaming_until_released)
    # **The queue is stopped until it is started** (`UX-006`, `T-181`), so a composed test that
    # expects bytes to move has to press Start exactly as a user does. Called on the manager
    # rather than through the toolbar because the seam under test here is not the control.
    composition.manager.start_queue()
    queue_three(composition, spin, downloads)

    # Recorded before the starts, and per job: `Progress` carries the count the table draws, and
    # the store's row does not, so the stream itself is the only place to see three of them.
    seen: dict[str, int] = dict.fromkeys(THREE_JOBS, 0)
    composition.manager.progress.connect(
        lambda message: seen.__setitem__(message.job_id, seen.get(message.job_id, 0) + 1)
    )

    for job_id in THREE_JOBS:
        composition.manager.start(job_id)
    held = composition.manager.active_job_ids()
    assert set(held) == set(THREE_JOBS), (
        f"the manager is holding {held} rather than the three jobs just started, so nothing "
        "below measures an application with three downloads in it"
    )

    assert spin(
        lambda: all(
            (job := composition.store.get(job_id)) is not None and job.status is JobStatus.RUNNING
            for job_id in THREE_JOBS
        ),
        timeout=120,
    ), (
        "three jobs never ran at the same moment, so there was no concurrency to measure: "
        f"{statuses_of(composition)}"
    )

    try:
        before = dict(seen)
        worst = 0.0
        passes = 0
        window = time.monotonic() + SAMPLE_WINDOW
        while time.monotonic() < window:
            started = time.perf_counter()
            qapp.processEvents()
            worst = max(worst, time.perf_counter() - started)
            passes += 1
            time.sleep(0.001)

        advanced = {job_id: seen[job_id] - before[job_id] for job_id in THREE_JOBS}
    finally:
        # Released even if an assertion above fired: three workers spinning on a file that never
        # arrives would outlive the test.
        (downloads / RELEASE_MARKER).write_text("stop", encoding="utf-8")

    assert all(advanced.values()), (
        f"the {SAMPLE_WINDOW} s of latency measured above was not taken while three downloads "
        f"were streaming — updates received per job during it: {advanced}"
    )
    assert passes, "the event loop was never sampled"
    # **The number, not just the verdict.** A pass says the margin was positive and nothing else;
    # three runs of this in the junit XML say whether it is shrinking. `cold_start_seconds` and
    # the network download record theirs for the same reason.
    record_property("worst_event_loop_pass_ms", round(worst * 1000, 1))
    record_property("progress_updates_delivered", sum(advanced.values()))
    assert worst < BUDGET, (
        f"one pass of the event loop took {worst * 1000:.1f} ms while three downloads were "
        f"running, against NFR-001's ~{BUDGET * 1000:.0f} ms interaction budget "
        f"({passes} passes sampled, {sum(advanced.values())} updates delivered)"
    )

    # And they finish, because a criterion about downloads running is not met by downloads that
    # only started.
    assert spin(
        lambda: all(
            (job := composition.store.get(job_id)) is not None and job.status is JobStatus.COMPLETED
            for job_id in THREE_JOBS
        ),
        timeout=120,
    ), f"the workers were released and the jobs never completed: {statuses_of(composition)}"


# --- T-102 / ARC-008: the corrupt-settings report, through the assembled application -------


def test_a_corrupt_settings_file_is_reported_through_the_composed_application(
    qapp: QApplication,
    tmp_path: Path,
    composed: Callable[..., application.Composition],
) -> None:
    """`ARC-008`, `T-102`: the seam between `load()` and the window is the half that can be wired
    wrong while both ends pass their own tests.

    `core` cannot show a dialog and composition has no window when it reads the file, so the
    diagnostic has to travel as data and be presented after the window exists. Nothing below the
    composed application is stubbed: a real malformed file on disk, the real `compose()`, and the
    real dialog it opens.
    """
    from tracks_and_trails.core import settings as app_settings

    settings_file = tmp_path / "settings.toml"
    settings_file.write_text("[queue]\nconcurrency = = 3\n", encoding="utf-8")

    composition = composed(settings_file=settings_file)
    _report_as_run_does(composition)

    dialog = composition.window.findChild(QMessageBox, "settingsProblemDialog")
    assert dialog is not None, (
        "a corrupt settings file started the application silently; ARC-008 requires the user be "
        "told that defaults are in force, and the seam between load() and the window is where "
        "that gets lost"
    )
    try:
        assert str(settings_file) in dialog.text()
        assert "default settings are in use" in dialog.text()
        # The fallback itself is unchanged: the application runs on defaults rather than refusing.
        assert composition.manager.concurrency == app_settings.CONCURRENCY_DEFAULT
    finally:
        dialog.close()


def test_an_ordinary_settings_file_opens_no_dialog(
    qapp: QApplication,
    tmp_path: Path,
    composed: Callable[..., application.Composition],
) -> None:
    """The silent half, and the one an over-eager implementation breaks.

    A first run has no file at all, and a good file has nothing to report. Either opening a warning
    box would make the report worthless — a dialog that appears every launch is one nobody reads.
    """
    absent = tmp_path / "never-written.toml"
    composition = composed(settings_file=absent)
    assert composition.window.findChild(QMessageBox, "settingsProblemDialog") is None, (
        "a first run opened a settings warning"
    )

    good = tmp_path / "good.toml"
    good.write_text("[queue]\nconcurrency = 4\n", encoding="utf-8")
    # A **different database**, because the first composition still holds the single-instance lock
    # on the default one (`T-087`, `A-004`). Two instances against different databases harm nothing
    # and must both start, which is one of that task's criteria — this is it, incidentally.
    second = composed(settings_file=good, database=tmp_path / "second.db")
    assert second.window.findChild(QMessageBox, "settingsProblemDialog") is None, (
        "a perfectly good settings file opened a warning"
    )
    assert second.manager.concurrency == 4


def test_a_second_composition_against_one_database_is_refused(
    qapp: QApplication,
    tmp_path: Path,
    composed: Callable[..., application.Composition],
) -> None:
    """`T-087`, `A-004`: the guard is taken by `compose()`, before anything opens the database.

    Through the real composition rather than the lock alone, because the ordering is the part that
    can be wired wrong: recovery rewrites rows on the line after `db.connect`, so a guard taken
    afterwards would let a second launch rewrite a live instance's in-flight jobs before refusing.
    """
    from tracks_and_trails.core.instance_lock import AlreadyRunningError

    database = tmp_path / "shared.db"
    first = composed(database=database)
    assert first.instance.is_held

    with pytest.raises(AlreadyRunningError, match="already using"):
        composed(database=database)


def test_the_lock_is_released_only_after_the_database_is_closed(
    qapp: QApplication,
    tmp_path: Path,
    spin: Callable[..., bool],
    composed: Callable[..., application.Composition],
) -> None:
    """Ownership outlives the last write, so the next launch never opens a half-closed database."""
    database = tmp_path / "shared.db"
    composition = composed(database=database)
    # Locals both sides of the shutdown, for the reason above: narrowing from the first assert
    # otherwise makes the second one — and everything after it — unreachable to mypy.
    held = composition.instance.is_held
    assert held

    composition.shutdown.begin()
    assert spin(lambda: composition.shutdown.finished, timeout=30), "shutdown never completed"

    released = composition.instance.is_held
    assert not released, (
        "the lock outlived the shutdown lifecycle, so a relaunch would be refused by a process "
        "that has finished with the database"
    )
    # And the next launch really can start.
    composed(database=database)


def test_interrupted_jobs_are_recovered_and_offered_by_the_composed_application(
    tmp_path: Path,
    qapp: QApplication,
    composed: Callable[..., application.Composition],
) -> None:
    """`T-082` end to end: **the seam, which is where an offer gets lost.**

    `recover_interrupted` returned its ids all along and composition threw them away, so the
    recovery was correct and invisible. Nothing below `compose()` is stubbed here — a real
    database carrying a row left `RUNNING`, the real recovery, and the real dialog.
    """
    from tracks_and_trails.core.job_state import JobStatus
    from tracks_and_trails.core.models import DownloadRequest, Job
    from tracks_and_trails.persistence import db
    from tracks_and_trails.persistence.repositories import JobRepository

    database = tmp_path / "library.sqlite3"
    request = DownloadRequest(
        url="https://example.invalid/clip",
        output_directory=str(tmp_path),
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )
    seeded = JobRepository(db.connect(database))
    seeded.append([Job(id=f"job-{n}", url=request.url, request=request) for n in range(3)])
    for index in range(3):
        for status in (JobStatus.PROBING, JobStatus.READY, JobStatus.RUNNING):
            stored = seeded.get(f"job-{index}")
            assert stored is not None
            seeded.update(stored.with_status(status))
    seeded._connection.close()

    composition = composed(database=database)

    dialog = composition.window.findChild(QMessageBox, "interruptedJobsDialog")
    assert dialog is not None, (
        "three jobs were left running by an unclean exit and the application started as though "
        "nothing had happened; the recovery is silent by design and the offer is what REQ-012 "
        "asks for"
    )
    assert "3 downloads were interrupted" in dialog.text()

    # And nothing restarted on its own, which is the other half of the criterion.
    for index in range(3):
        job = JobRepository(db.connect(database)).get(f"job-{index}")
        assert job is not None
        assert job.status is JobStatus.FAILED
    dialog.close()


def test_choosing_a_format_on_a_queued_row_changes_the_durable_request(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """`UX-005` §6 / `T-126`, asserted on **the stored request** rather than on the label.

    That distinction is `T118-R6`: the add dialog once updated the displayed selector and nothing
    else, so it showed one format and queued another — `AGENTS.md` §10's `Critical` row,
    downloading something other than what the user chose, silently. A row control that changed only
    what the row says would be the same defect in a new place, and a test reading the row back
    would agree with it.

    So this drives the model the way an editor does, then reads the job out of the **store**.
    """
    composition = composed(entry_point=child_probing_then_waiting)
    queue_three(composition, spin, tmp_path / "downloads", template=CUSTOM_TEMPLATE)
    # **Refreshed explicitly**, because `queue_three` writes through the store rather than through
    # the add dialog — and adding is the one queue change nothing announces, which is why the
    # dialog's `finished` signal calls this in the real application.
    composition.window.refresh_queue()
    view = composition.window.queue_view
    assert view is not None
    assert spin(lambda: "job-1" in view.model.job_ids(), timeout=60), "the row never appeared"

    before = composition.store.get("job-1")
    assert before is not None

    custom = CUSTOM_TEMPLATE
    assert custom != presets.DEFAULT_OUTPUT_TEMPLATE
    assert before.request.output_template == custom
    chosen = presets.by_name("Audio only (original)")
    assert before.request.format_selector != chosen.format_selector, (
        "the row already has the format this test is about to choose, so it would pass without "
        "anything changing"
    )

    row = view.model.row_of("job-1")
    assert row is not None
    assert view.model.setData(view.model.index(row, 0), chosen.name, PRESET_ROLE)

    assert spin(
        lambda: (
            (job := composition.store.get("job-1")) is not None
            and job.request.format_selector == chosen.format_selector
            # **The naming the row already had, not the preset's** (`T-195`). A shipped preset
            # states no template; retargeting changes the format and must leave the filename
            # alone, or choosing a different format would silently rename the download.
            #
            # `T195-R4`: this started from the *shipped* template, so dropping
            # `default_output_template=job.request.output_template` produced the same string and
            # left the assertion green. The row is given a deliberately custom template below,
            # which the broken implementation cannot produce.
            and job.request.output_template == custom
        ),
        timeout=60,
    ), (
        "the format chosen on the row never reached the stored request: "
        f"{stored.request if (stored := composition.store.get('job-1')) is not None else None}"
    )

    # And the row agrees with what is stored, which is the other half of `T118-R6` — the two
    # disagreeing is the defect, and either one alone is half the claim.
    assert spin(
        lambda: view.model.data(view.model.index(row, 0), PRESET_ROLE) == chosen.name, timeout=60
    ), "the stored request changed and the row still reports the old format"


# --- T-180: the partition, through the wiring composition actually builds ------------------


def test_two_databases_get_two_thumbnail_caches_through_composition(
    composed: Callable[..., application.Composition],
    qapp: QApplication,
    tmp_path: Path,
    spin: Callable[..., bool],
) -> None:
    """**`T180-R2`.** The partition asserted at the seam that derives it, not at the helper.

    The first version of this proof derived two roots itself, wrote both files by hand and built
    **one** store. That shows `cache_root_for` separates roots handed to it — and it stays green if
    `compose` stops deriving a root from the database, or if `MainWindow` stops passing one to the
    store it builds. The production seam was outside the gate, which is the finding.

    So this builds **two whole applications** over two databases and reads the store each one's own
    queue view actually holds. Nothing here names `cache_root_for`: if the wiring is cut anywhere
    between the database path and the widget that sweeps, the two roots collapse into one and the
    sweep reaches the other instance's picture — which is `ARC-006`'s permitted second instance
    losing its cache, and the whole of `T-180`.
    """
    cache = tmp_path / "cache"
    first = composed(database=tmp_path / "one.sqlite3", cache_directory=cache)
    second = composed(database=tmp_path / "two.sqlite3", cache_directory=cache)

    assert first.cache_root != second.cache_root, (
        "composition handed two databases one cache root; every sweep now reaches the other's files"
    )

    ours = first.window.queue_view
    theirs = second.window.queue_view
    assert ours is not None and theirs is not None

    # Written through each store's *own* resolved path, so a store built with the wrong root puts
    # its file in the wrong place and the assertions below fail rather than silently pass.
    unnamed = "https://pics.invalid/ours-and-unnamed.jpg"
    live = "https://pics.invalid/theirs-and-live.jpg"
    for url, composition in ((unnamed, first), (live, second)):
        path = thumbnail_cache_path(url, composition.cache_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"a picture")

    # One instance sweeps, naming nothing: everything in *its* directory is collectable and
    # nothing in anyone else's is reachable.
    ours.thumbnails.sweep(())

    assert spin(lambda: not thumbnail_cache_path(unnamed, first.cache_root).exists(), timeout=60), (
        "the sweeping instance did not collect its own unnamed picture, so this proves nothing"
    )
    assert thumbnail_cache_path(live, second.cache_root).exists(), (
        "one instance's sweep deleted another database's live picture — T-180's defect, reached "
        "through the composition that builds the wiring rather than through the helper"
    )


def test_the_window_hands_the_partitioned_root_to_both_of_its_stores(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """`T180-R2`'s other half: the queue's store and the add dialog's must share one root.

    `cache_generation` is keyed by directory precisely so a picture the add dialog publishes is one
    the queue's sweep can still see (`T118-R16`). Two roots would put that count back out of reach —
    and a window that partitioned only the queue's store would pass the test above while leaving the
    dialog writing into the shared location this task exists to empty.
    """
    composition = composed(database=tmp_path / "one.sqlite3", cache_directory=tmp_path / "cache")
    view = composition.window.queue_view
    assert view is not None

    dialog = composition.window.open_add_dialog()
    try:
        assert view.thumbnails.cache_root == composition.cache_root, (
            "the queue's store did not get the partitioned root"
        )
        assert dialog.thumbnails.cache_root == composition.cache_root, (
            "the add dialog's store did not get the partitioned root, so a picture it publishes "
            "lands outside the directory the queue's sweep accounts for"
        )
    finally:
        dialog.deleteLater()


def test_a_stored_ffmpeg_location_is_what_the_application_resolves(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """**`T-199`'s criterion, through a real resolution rather than the stored value.**

    *"The screen sets an ffmpeg location, it persists, and the resolution path prefers it over
    `PATH`"* — and the second half is the one that fails quietly. So this composes against a
    settings file that already names an ffmpeg, with a `PATH` that also has one, and asserts on
    what `find_ffmpeg` actually returned: the stored file, not the one `PATH` would have found.

    The stand-in is a real executable file rather than a mocked flag, because `find_ffmpeg`
    applies the platform's own executable-discovery rules and a mock would assert nothing about
    them.
    """
    elsewhere = tmp_path / "somewhere-else"
    elsewhere.mkdir()
    chosen = an_executable_ffmpeg(elsewhere)
    settings_file = tmp_path / "settings.toml"
    assert (
        core_settings.save(
            core_settings.with_ffmpeg_location(core_settings.Settings(), chosen), settings_file
        )
        is None
    )

    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)

    assert composition.ffmpeg.path == chosen, (
        f"the application resolved {composition.ffmpeg.path}, not the location the settings file "
        "names — the setting is stored and does not run"
    )
    assert composition.ffmpeg.available
    # `T-192`'s gate line, and `T-199`'s criterion that it reflects an *overridden* ffmpeg.
    assert "ffmpeg found" in composition.ffmpeg.summary()


def test_an_unusable_stored_ffmpeg_location_still_starts_the_application(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """`ARC-008`: report and fall back, and **the application still starts** (`REQ-024`).

    A missing ffmpeg is a loss of features, never a failure to run — so the assertion is that
    composition completed at all, and that what it reports names the features rather than a path
    the user cannot act on.
    """
    settings_file = tmp_path / "settings.toml"
    settings_file.write_text(
        f"[ffmpeg]\nlocation = {json.dumps(str(tmp_path / 'gone' / 'ffmpeg'))}\n",
        encoding="utf-8",
    )

    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)

    assert composition.window is not None, "an unusable ffmpeg location stopped the application"
    read = core_settings.load(settings_file)
    assert read.settings.ffmpeg_location is None
    assert read.problem is not None and "does not exist" in read.problem.reason


def test_no_preset_the_worker_would_refuse_is_offered_when_ffmpeg_is_absent(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """**`T199-R1`.** `UX-005` §5, over the whole add dialog rather than one screen of it.

    The first version of this task gated `OptionsDialog` and left the preset catalogue alone, so
    `Audio only (MP3)`, `Audio only (original)` and `Video with embedded subtitles` were still
    offered with ffmpeg absent — and the worker's `_ffmpeg_gap` refuses every one of them before a
    byte moves. Offering what will be refused is precisely what that rule forbids.

    **A real absent-ffmpeg resolution, not a mocked flag**, which the criterion asks for: the
    override names a file that does not exist, so `find_ffmpeg` reports unavailable through its own
    logic and composition carries that answer into the dialog the way it always does.

    Asserted against `needs_ffmpeg` rather than a list of names, so a preset added to the catalogue
    is covered without this test being edited — the enumeration and the offer, compared.
    """
    composition = composed(
        ffmpeg_override=tmp_path / "no-ffmpeg-here", entry_point=child_probing_then_waiting
    )
    assert not composition.ffmpeg.available, "this environment has ffmpeg, so it proves nothing"

    dialog = composition.window.open_add_dialog()
    assert dialog is not None
    try:
        offered = dialog.presets
        assert offered, "the dialog offers no presets at all, which is not a usable dialog"
        refused = [preset.name for preset in offered if core_presets.needs_ffmpeg(preset)]
        assert not refused, (
            f"{refused} are offered with ffmpeg absent, and the worker refuses each of them "
            "before downloading. UX-005 §5: nothing is drawn that would be refused"
        )
        # The other direction, so the gate cannot pass by offering nothing: what does not need
        # ffmpeg is still there.
        assert any(not core_presets.needs_ffmpeg(preset) for preset in offered)
    finally:
        dialog.close()
        QApplication.processEvents()


def test_choosing_an_ffmpeg_reaches_the_workers_that_start_afterwards(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """**`T199-R2`.** The setting has to change what runs, not only what the window says.

    `DownloadManager` captures the override at construction and hands it to every child it starts.
    Nothing updated it, so after a live change the UI followed the new answer while workers still
    received the old path — the dialog offering exactly what the worker would then refuse.

    Asserted on the value the manager passes to children, which is the thing that was wrong;
    asserting the status line would have passed against the defect.
    """
    composition = composed(
        ffmpeg_override=tmp_path / "absent", entry_point=child_probing_then_waiting
    )
    assert composition.manager._ffmpeg_override is None

    chosen = an_executable_ffmpeg(tmp_path)
    screen = composition.window.open_settings()
    assert screen is not None, "the composed window offers no settings screen"
    try:
        write_location = composition.window._on_ffmpeg_location_chosen
        assert write_location is not None, "composition wired no ffmpeg writer"
        write_location(chosen)  # the route the screen's button takes
        QApplication.processEvents()

        assert composition.manager._ffmpeg_override == chosen, (
            f"workers would still be handed {composition.manager._ffmpeg_override}, not the "
            "ffmpeg the user just chose"
        )
    finally:
        screen.close()
        QApplication.processEvents()


def test_an_unusable_choice_is_refused_the_same_way_however_it_arrives(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """**`T199-R3`.** One report-and-fallback contract, not three that disagree.

    Validation was split and answered differently by route: a *stored* value was checked at load,
    a *live* choice was checked nowhere and persisted regardless, and `find_ffmpeg` refused a bad
    override without falling back — so the same unusable path produced a different outcome
    depending on how it arrived, and an executable named `ls` was accepted as ffmpeg live because
    the name check existed only on the load path.

    Driven through the live route, which is the one that had no checks at all, over the three
    shapes the criterion names. Each must end the same way: **the choice is refused, the setting is
    unchanged, and the application is still resolving ffmpeg some other way.**
    """
    composition = composed(entry_point=child_probing_then_waiting)
    unchanged = composition.manager._ffmpeg_override

    not_ffmpeg = tmp_path / "ls"
    not_ffmpeg.write_text("#!/bin/sh\nexit 0\n")
    not_ffmpeg.chmod(0o755)
    a_folder = tmp_path / "a-folder"
    a_folder.mkdir()

    write_location = composition.window._on_ffmpeg_location_chosen
    assert write_location is not None, "composition wired no ffmpeg writer"
    for label, candidate in (
        ("missing", tmp_path / "not-here" / "ffmpeg"),
        ("a folder", a_folder),
        ("executable but not ffmpeg", not_ffmpeg),
    ):
        write_location(candidate)
        QApplication.processEvents()

        assert composition.store is not None
        read = core_settings.load(composition.settings_path)
        assert read.settings.ffmpeg_location is None, (
            f"{label} was persisted as the ffmpeg location, so it would fail again next launch"
        )
        said = composition.window.statusBar().currentMessage()
        assert "PATH" in said, (
            f"{label} was refused without saying so: the status bar reads {said!r}"
        )
        assert composition.manager._ffmpeg_override == unchanged, (
            f"{label} changed what workers receive despite being refused"
        )


def test_compose_carries_the_settings_problem_and_does_not_open_it(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """`T-308`: `compose()` may not open a modal on a window nobody has shown yet.

    The maintainer's launch on 2026-09-09 put this dialog **behind** the main window and blocked
    it: `open()` makes it window-modal, and the parent was mapped afterwards, so the compositor
    stacked the window over a dialog that had never been a visible transient child.

    Asserted from both ends — the problem is carried, and nothing is shown — because either alone
    passes for the wrong reason. Carrying it without showing it would be silence, which `ARC-008`
    forbids; showing it without carrying it is where this started.
    """
    settings_file = tmp_path / "settings.toml"
    settings_file.write_text("this is not toml at all\n", encoding="utf-8")

    composition = composed(settings_file=settings_file)
    QApplication.processEvents()

    assert composition.settings_problem is not None, (
        "the file cannot be parsed and nothing was carried; ARC-008 requires a report"
    )
    assert not composition.window.findChildren(QMessageBox, "settingsProblemDialog"), (
        "compose() opened the dialog itself, which is T-308: run() has not shown the window yet"
    )


def test_the_settings_problem_is_a_visible_child_of_a_shown_window(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """`T-308`'s other half: reported *after* the window, and belonging to it.

    **A constructed box is not a shown one**, and the defect was entirely about when. So this
    shows the window first, reports as `run()` does, and asks Qt what it got: a visible box whose
    parent is the window, which is what makes it a transient the compositor keeps above.

    **Stacking itself is the compositor's and is not asserted here.** Offscreen has no stacking to
    read, and `T-288` is this project's reminder that a Wayland-only behaviour is not visible from
    a headless run. `T-308` requires the real-display check on Wayland and X11 separately.
    """
    settings_file = tmp_path / "settings.toml"
    settings_file.write_text("still not toml\n", encoding="utf-8")

    composition = composed(settings_file=settings_file)
    composition.window.show()
    QApplication.processEvents()
    _report_as_run_does(composition)
    QApplication.processEvents()

    shown = composition.window.findChildren(QMessageBox, "settingsProblemDialog")
    assert shown, "nothing was shown after the window appeared"
    try:
        box = shown[0]
        assert box.isVisible(), "the box exists but was never shown"
        assert box.parent() is composition.window, (
            "the box is not a child of the window, so the compositor has no parent to keep it above"
        )
        assert composition.window.isVisible(), "the window must already be up when this appears"
    finally:
        for box in shown:
            box.close()
        QApplication.processEvents()


def test_the_stacking_probe_cannot_reach_an_inherited_profile(tmp_path: Path) -> None:
    """`T308-R3`: the diagnostic tool wrote to a queue outside the profile it created.

    It replaced `XDG_CONFIG_HOME` and used `setdefault` for the data and cache roots, so an
    inherited `XDG_DATA_HOME` stayed pointed at the real profile while the file claimed isolation.
    `compose()` opens that database and runs `recover_interrupted()` before any window appears, and
    a reviewer's canary went from `RUNNING` to `FAILED / INTERRUPTED` because of it — **exit code
    0, no warning**.

    This is the reviewer's reproduction, kept: seed a canary in an inherited profile, run the tool
    as a child with those roots exported, and require the canary to be exactly as it was. A tool
    that rewrites a queue is worse than no tool, so the guard is a test rather than a comment.
    """
    inherited = tmp_path / "inherited"
    for child in ("config", "data", "cache"):
        (inherited / child).mkdir(parents=True)
    environment = {
        **os.environ,
        "XDG_CONFIG_HOME": str(inherited / "config"),
        "XDG_DATA_HOME": str(inherited / "data"),
        "XDG_CACHE_HOME": str(inherited / "cache"),
        "QT_QPA_PLATFORM": "offscreen",
    }

    seed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, 'src')\n"
            "from tracks_and_trails.persistence import db\n"
            "from tracks_and_trails.persistence.repositories import JobRepository\n"
            "from tracks_and_trails.core.models import DownloadRequest, Job\n"
            "from tracks_and_trails.core.job_state import JobStatus\n"
            "path = db.database_path()\n"
            "print(path)\n"
            "with db.open_database(path) as connection:\n"
            "    request = DownloadRequest(url='https://example.invalid/v',"
            " output_directory='/tmp', format_selector='best',"
            " output_template='%(title)s.%(ext)s')\n"
            "    JobRepository(connection).add(Job(id='isolation-canary',"
            " url='https://example.invalid/v', request=request, status=JobStatus.RUNNING))\n",
        ],
        capture_output=True,
        text=True,
        env=environment,
        cwd=REPOSITORY_ROOT,
        check=False,
    )
    assert seed.returncode == 0, seed.stderr
    canary_database = Path(seed.stdout.strip().splitlines()[-1])
    assert canary_database.exists(), "the canary database was not created where it was expected"
    before = canary_database.read_bytes()

    probe = subprocess.run(
        [sys.executable, "tools/t308_warning_stacking_probe.py"],
        capture_output=True,
        text=True,
        env=environment,
        cwd=REPOSITORY_ROOT,
        check=False,
    )

    assert canary_database.read_bytes() == before, (
        "the probe altered a database outside the profile it created — T308-R3, and the exit "
        f"code was {probe.returncode}, which is how it went unnoticed"
    )


def test_present_shows_the_window_before_it_reports(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`T308-R2`: driven through the production sequence, not through a helper in this file.

    The first guards called the reporting themselves, so **deleting `run()`'s branch passed all
    seven of them** — the reviewer's finding, and a fair one: a test that performs the step it is
    checking measures nothing about production. `app.present` is that sequence extracted, because
    `run()` builds its own `QApplication` and cannot be called from a session that has one.

    **The recorded fact is visibility at the moment of reporting**, which is the property. Removing
    the report fails this because nothing is recorded; moving it before `show()` fails it because
    the window is not up yet. Both are the defect, and neither was caught before.
    """
    settings_file = tmp_path / "settings.toml"
    settings_file.write_text("not toml\n", encoding="utf-8")
    composition = composed(settings_file=settings_file)

    seen: list[bool] = []
    original = type(composition.window).report_settings_problem

    def recording(window: MainWindow, problem: SettingsProblem) -> object:
        seen.append(window.isVisible())
        return original(window, problem)

    monkeypatch.setattr(type(composition.window), "report_settings_problem", recording)

    application.present(composition)
    QApplication.processEvents()

    assert seen, "present() never reported the carried problem"
    assert seen == [True], (
        "the warning was reported while the window was still hidden, which is T-308: a "
        "window-modal dialog on an unmapped parent is stacked behind it and still blocks it"
    )
    for box in composition.window.findChildren(QMessageBox, "settingsProblemDialog"):
        box.close()
    QApplication.processEvents()


def _report_as_run_does(composition: application.Composition) -> None:
    """Show the carried settings problem the way `run()` does, after the window exists.

    **`compose()` no longer opens the box** (`T-308`): it opened a window-modal dialog on a parent
    `run()` had not shown yet, so the compositor stacked the window over a dialog that had never
    been a visible transient child — a modal nobody could see blocking a window nobody could use.
    The problem is carried and `run()` shows it, so a test about *what the user is told* has to do
    the same one step. What it must not do is assert that `compose()` shows it, which is the
    behaviour that was wrong.
    """
    if composition.settings_problem is not None:
        composition.window.report_settings_problem(composition.settings_problem)


def test_a_stored_ffmpeg_that_cannot_be_run_is_reported_not_just_logged(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """**`T199-R3`, first half.** `ARC-008` says *report*, and a log line is not a report.

    A stored location that exists, is a file and is named for ffmpeg passes everything `load()`
    can ask — whether it can actually be **run** is the platform's answer, through `find_ffmpeg`,
    and `core/` may not ask it. So this shape reached the fallback with nothing shown to the user:
    the resolution quietly became `PATH` and the settings dialog never appeared, which is
    reverting silently by another name.

    Composition contributes the problem, because composition is the layer that can. Asserted on the
    dialog a user would actually see rather than on a log record.
    """
    unrunnable = tmp_path / "ffmpeg"
    unrunnable.write_text("not executable\n", encoding="utf-8")
    unrunnable.chmod(0o644)
    settings_file = tmp_path / "settings.toml"
    settings_file.write_text(
        f"[ffmpeg]\nlocation = {json.dumps(str(unrunnable))}\n", encoding="utf-8"
    )

    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)
    _report_as_run_does(composition)
    QApplication.processEvents()

    assert composition.ffmpeg.path != unrunnable, "an unrunnable file was accepted as ffmpeg"
    shown = composition.window.findChildren(QMessageBox, "settingsProblemDialog")
    assert shown, (
        "the stored ffmpeg cannot be run and nothing told the user: ARC-008 requires a report, "
        "not a silent fallback"
    )
    try:
        assert "cannot be run" in shown[0].text()
        assert str(unrunnable) in shown[0].text(), "the report does not name the file it discarded"
    finally:
        for box in shown:
            box.close()
        QApplication.processEvents()


def test_refusing_a_choice_leaves_a_working_override_exactly_where_it_was(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """**`T199-R3`, second half — and the state my own regression could not see.**

    The refusal path reported and returned, but only *after* pushing the fallback into the
    environment and into `set_ffmpeg_override`. So with a good custom override in force, refusing a
    bad new choice switched future workers to `PATH` while the stored setting and the screen went
    on naming the custom binary — `T199-R2`'s UI/worker disagreement, recreated through the door
    marked *nothing changes*.

    **The earlier test started from `PATH`**, where the fallback and the previous value are the
    same object, so its "unchanged" assertion was true for the wrong reason. This one starts from a
    working custom override, which is the only state that can tell the two apart.
    """
    good_dir = tmp_path / "good"
    good_dir.mkdir()
    good = an_executable_ffmpeg(good_dir)
    settings_file = tmp_path / "settings.toml"
    assert (
        core_settings.save(
            core_settings.with_ffmpeg_location(core_settings.Settings(), good), settings_file
        )
        is None
    )

    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)
    assert composition.manager._ffmpeg_override == good, (
        "the working custom override was not in force to begin with, so this proves nothing"
    )

    write_location = composition.window._on_ffmpeg_location_chosen
    assert write_location is not None
    write_location(tmp_path / "does-not-exist" / "ffmpeg")
    QApplication.processEvents()

    assert composition.manager._ffmpeg_override == good, (
        f"a refused choice moved future workers to {composition.manager._ffmpeg_override}, away "
        "from the override that is still stored and still displayed"
    )
    assert core_settings.load(settings_file).settings.ffmpeg_location == good, (
        "a refused choice changed the stored setting"
    )
    # **The displayed state too, because the handoff claimed it and this did not assert it.**
    # Non-blocking review note, fixed rather than argued: production passed a direct probe, but a
    # claim the test does not make is the recurring shape of every finding on this task.
    assert composition.window._ffmpeg_location == good, (
        f"the window now shows {composition.window._ffmpeg_location} after a refusal, so the "
        "screen and the stored setting disagree"
    )
    screen = composition.window.open_settings()
    assert screen is not None
    try:
        shown = screen.findChild(QLabel, "ffmpegLocationValue")
        assert shown is not None and shown.text() == str(good), (
            f"the settings screen reads {shown.text() if shown else None!r} after a refused "
            f"choice, not the override still in force"
        )
    finally:
        screen.close()
        QApplication.processEvents()


def test_a_short_cookie_path_is_redacted_by_the_assembled_application(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """**`T197-R1`, reopened at `4c48273` — and asserted through `compose`, which is the point.**

    `/a` is a legal cookie path, two bytes long, and *already* absolute — so the previous
    correction's trick of registering a longer absolute spelling has nothing to reach for. It
    survived the real `ARC-008` refusal.

    **The unit gate could not have caught the regression this guards against.** Its version called
    `remember_a_path` itself, so reverting composition to the floored `remember_a_secret` left it
    green — the test agreed with the intended wiring rather than reading the real one. This builds
    the application and asks the redaction sink what `compose` actually registered, so changing
    that call is what fails.
    """
    settings_file = tmp_path / "settings.toml"
    settings_file.write_text('[cookies]\nfile = "/a"\n', encoding="utf-8")

    app_logging.forget_the_secrets()
    try:
        composed(settings_file=settings_file, entry_point=child_probing_then_waiting)

        # The written value is `/a` either way — it comes from the file, not from a `Path` — but
        # the *reported* spelling is `str(Path("/a"))`, which is `\a` on Windows. Asserted through
        # the same rendering the application uses, for the reason the runtime test above records.
        spelled = str(Path("/a"))
        line = f"settings: the cookies file {spelled} does not exist"
        assert spelled not in app_logging.redact(line), (
            "the assembled application did not register its own short cookie path: "
            f"{app_logging.redact(line)!r}"
        )
    finally:
        app_logging.forget_the_secrets()


def test_a_short_cookie_path_chosen_at_runtime_is_redacted_too(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """The other route into the same leak, and it needed its own test (`T197-R1`).

    A cookie file arrives two ways: read from `settings.toml` at startup, and **chosen while the
    application is running**. They register through different code, and a mutation reverting only
    the runtime one left every existing test green — including the startup test beside this. Two
    routes, two regressions.
    """
    settings_file = tmp_path / "settings.toml"
    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)

    choose = composition.window._on_cookie_file_chosen
    assert choose is not None, "composition wired no cookies writer"

    app_logging.forget_the_secrets()
    try:
        # **The path as *this platform* spells it, not as the literal was typed.** `Path("/a")`
        # renders `\a` on Windows, so a hardcoded `/a` in the asserted line matches nothing there
        # and the test passes without testing anything — it failed on the Windows job for exactly
        # that reason. What the application registers is what `str(path)` produces, so that is what
        # the line has to contain.
        short = Path("/a")
        choose(short)
        QApplication.processEvents()

        spelled = str(short)
        line = f"settings: the cookies file {spelled} does not exist"
        assert spelled not in app_logging.redact(line), (
            f"a cookie path chosen at runtime was not registered: {app_logging.redact(line)!r}"
        )
    finally:
        app_logging.forget_the_secrets()


def _settings_screen(composition: application.Composition) -> SettingsDialog:
    """The Settings screen, opened the way a user opens it (`T195-R4`).

    The previous round drove `composition.window._on_output_template_chosen` directly, which is
    composition's end of the wire. Removing the screen's half — the `on_*_chosen` arguments, or
    `refuse_template` — left those tests green, because nothing they touched went through
    `open_settings`. So the screen is opened, and the controls on it are what the tests operate.
    """
    screen = composition.window.open_settings()
    assert screen is not None, "composition wired no settings writers, so there is no screen"
    return screen


def test_choosing_a_template_on_the_screen_reaches_the_file_and_the_next_paste(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """**`REQ-023`, `T-195`, corrected twice — at `T195-R4` and again after it.**

    The first version bypassed both surfaces, calling `set_output_template` and `save` itself. The
    second called composition's callback directly, which still skipped `open_settings`. This types
    into the screen's own field.

    Three things have to hold together and only the last was ever really in doubt: the file gets it,
    **the next add dialog is built with it**, and the route from the control to composition exists
    at all.
    """
    settings_file = tmp_path / "settings.toml"
    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)
    chosen = "%(uploader)s/%(title)s.%(ext)s"

    screen = _settings_screen(composition)
    try:
        field = screen.findChild(QLineEdit, OUTPUT_TEMPLATE_NAME)
        assert field is not None, "the screen has no output-template field"
        field.setText(chosen)
    finally:
        screen.close()

    assert core_settings.load(settings_file).settings.output_template == chosen, (
        "typing into the screen's field never reached the file"
    )
    # **The durable request a worker would be given, and the path it renders to** (`T195-R4`).
    # Reading `dialog._default_output_template` proved the dialog was *built* with the value and
    # stopped there. This queues a row through the dialog and reads the request back out of the
    # database, then asks the manager where that request would write — which exercises the render
    # and the containment rule rather than the stored string.
    #
    # A file on disk would need a real download; `tests/integration/test_end_to_end.py` is where
    # that lives, and it is deliberately not this suite's job. What is proved here is that the
    # template reaches a persisted request and renders to a path under the chosen folder.
    dialog = composition.window.open_add_dialog()
    try:
        type_urls(dialog, "https://composed.invalid/named")
        dialog.resolve()
        assert spin(
            lambda: bool(dialog.rows) and all(row.committable for row in dialog.rows), timeout=60
        ), "the pasted URL never resolved"
        dialog.add_to_queue()
        assert spin(lambda: bool(dialog.queued_job_ids), timeout=30), "the row never persisted"
        job_id = dialog.queued_job_ids[0]
    finally:
        dialog.close()

    queued = composition.store.get(job_id)
    assert queued is not None
    assert queued.request.output_template == chosen, (
        "the template chosen on the settings screen never reached the queued request"
    )

    previewed = composition.manager.preview_output_path(
        queued.request,
        MediaInfo(
            url=queued.request.url,
            title="A download",
            uploader="An uploader",
            is_playlist=False,
        ),
    )
    assert previewed.refusal is None, previewed.refusal
    assert previewed.path.startswith(str(tmp_path)), previewed.path
    assert "An uploader" in previewed.path, (
        f"the rendered path does not use the chosen template: {previewed.path!r}"
    )


def test_a_refused_template_typed_into_the_screen_is_not_stored(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """`P-23` at the control rather than at the callback (`T195-R2`, `T195-R4`).

    A screen that shows the reason and stores the value anyway satisfies the visible half and
    leaves every future download named by a template that does not render.
    """
    settings_file = tmp_path / "settings.toml"
    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)

    screen = _settings_screen(composition)
    try:
        field = screen.findChild(QLineEdit, OUTPUT_TEMPLATE_NAME)
        note = screen.findChild(QLabel, OUTPUT_TEMPLATE_NOTE_NAME)
        assert field is not None and note is not None
        field.setText("../%(title)s.%(ext)s")

        assert note.text(), "no reason was shown for a template that escapes the folder"
    finally:
        screen.close()

    assert core_settings.load(settings_file).settings.output_template == "", (
        "a refused template was written to the file anyway"
    )


def test_two_settings_edits_in_a_row_do_not_erase_one_another(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """**`T195-R1`.** Each callback built new settings from `held.settings` and never advanced it.

    So the second edit was derived from the settings as they were at startup and wrote them back
    over the first. Driven through the screen's two controls, in one sitting, because that is how a
    user would meet it.
    """
    # **This test picks MP3, so it has to supply an ffmpeg** (`T195-R6`). The settings screen only
    # offers presets this installation can perform — `T195-R3`'s own fix — so on a host without
    # ffmpeg the combo has no MP3 entry, `findData` answers `-1`, and `setCurrentIndex(-1)` selects
    # nothing. The test then failed for a reason that had nothing to do with what it asserts.
    ffmpeg_here = an_executable_ffmpeg(tmp_path)
    settings_file = tmp_path / "settings.toml"
    composition = composed(
        settings_file=settings_file,
        ffmpeg_override=ffmpeg_here,
        entry_point=child_probing_then_waiting,
    )

    screen = _settings_screen(composition)
    try:
        combo = screen.findChild(QComboBox, DEFAULT_PRESET_NAME)
        field = screen.findChild(QLineEdit, OUTPUT_TEMPLATE_NAME)
        assert combo is not None and field is not None
        found = combo.findData(presets.AUDIO_MP3.name)
        assert found >= 0, "the screen does not offer the preset this test selects"
        combo.setCurrentIndex(found)
        field.setText("%(uploader)s/%(title)s.%(ext)s")
    finally:
        screen.close()

    stored = core_settings.load(settings_file).settings
    assert stored.default_preset == presets.AUDIO_MP3.name, (
        "the second edit was built from stale settings and erased the first"
    )
    assert stored.output_template == "%(uploader)s/%(title)s.%(ext)s"


def test_the_default_chosen_on_the_screen_is_what_a_staged_row_inherits(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """The criterion in the entry's own words: *a new paste actually inherits it*.

    Asserted against a **staged row**, not against the dialog's stored default — the entry asks for
    the row, and a row is what carries the choice into a request.
    """
    # **This test picks MP3, so it has to supply an ffmpeg** (`T195-R6`). The settings screen only
    # offers presets this installation can perform — `T195-R3`'s own fix — so on a host without
    # ffmpeg the combo has no MP3 entry, `findData` answers `-1`, and `setCurrentIndex(-1)` selects
    # nothing. The test then failed for a reason that had nothing to do with what it asserts.
    ffmpeg_here = an_executable_ffmpeg(tmp_path)
    settings_file = tmp_path / "settings.toml"
    composition = composed(
        settings_file=settings_file,
        ffmpeg_override=ffmpeg_here,
        entry_point=child_probing_then_waiting,
    )

    screen = _settings_screen(composition)
    try:
        combo = screen.findChild(QComboBox, DEFAULT_PRESET_NAME)
        assert combo is not None
        found = combo.findData(presets.AUDIO_MP3.name)
        assert found >= 0, "the screen does not offer the preset this test selects"
        combo.setCurrentIndex(found)
    finally:
        screen.close()

    dialog = composition.window.open_add_dialog()
    try:
        type_urls(dialog, "https://composed.invalid/inherits")
        assert spin(lambda: bool(dialog.rows), timeout=60), "the pasted URL never staged"
        assert dialog.preset_for(dialog.rows[0]).name == presets.AUDIO_MP3.name, (
            "the staged row did not inherit the default chosen on the settings screen"
        )
    finally:
        dialog.close()


def test_a_template_the_editor_would_refuse_is_refused_by_the_screen_too(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """**`T195-R2`.** The first build checked field names only.

    `unsupported_refusal` answers *is every `%(field)s` one we can fill* — and nothing else. So
    `%(title`, which yt-dlp's own parser rejects, and `../%(title)s.%(ext)s`, which escapes the
    download folder, were both accepted and written. The row editor refuses both, through
    `preview_output_path`, and the two surfaces must not disagree about what is usable.
    """
    settings_file = tmp_path / "settings.toml"
    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)
    refuse = composition.window._refuse_template

    assert refuse("%(title") is not None, "malformed syntax was accepted"
    assert refuse("../%(title)s.%(ext)s") is not None, "a template escaping the folder was accepted"
    assert refuse("%(nonsense)s.%(ext)s") is not None, "an unfillable field was accepted"
    assert refuse("%(uploader)s/%(title)s.%(ext)s") is None, (
        "a usable template was refused, which would make the setting unsettable"
    )


def test_an_unusable_stored_template_is_reported_and_the_application_still_starts(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """**`ARC-008` and `T195-R2`, from disk rather than from the screen.**

    `load()` cannot make this check: it lives in `core/`, and the authority needs yt-dlp's syntax
    parser and the containment rule, which are the manager's. So a hand-edited file reached the
    application unvalidated. It is re-asked once the manager exists — reported, cleared so the
    shipped default applies, and the application starts either way.
    """
    settings_file = tmp_path / "settings.toml"
    settings_file.write_text('output_template = "%(title"\n', encoding="utf-8")

    # **The report the user actually sees** (`T195-R4`, twice). `ARC-008`'s rule is that a
    # discarded setting is *reported*, not silently corrected — so asserting the fallback alone
    # would pass an implementation that reverted in silence, which is the whole defect.
    #
    # The first correction read the log instead, on the belief that driving the message box needed
    # a nested event loop. It does not: `report_settings_problem` names its dialog, and the
    # corrupt-settings test above has been finding it with `findChild` since `T-102`. A log line is
    # not what `ARC-008` promises.
    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)
    _report_as_run_does(composition)

    shown = composition.window.findChild(QMessageBox, "settingsProblemDialog")
    assert shown is not None, "the refused stored template was discarded without telling anyone"
    said = f"{shown.text()}\n{shown.informativeText()}\n{shown.detailedText()}"
    assert "output_template" in said, said
    shown.close()

    dialog = composition.window.open_add_dialog()
    try:
        assert dialog._default_output_template == presets.DEFAULT_OUTPUT_TEMPLATE, (
            "a refused stored template is still being used to name downloads"
        )
    finally:
        dialog.close()


def test_the_settings_screen_offers_only_presets_this_installation_can_perform(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """**`T195-R3`.** The screen offered a default the next paste silently did not inherit.

    `AddUrlDialog` drops presets that need an ffmpeg this installation does not have. The settings
    combo was handed the *whole* catalogue — so with ffmpeg absent, choosing `Audio only (MP3)` as
    the default was accepted and stored, and the next paste started on `Best video up to 1080p`
    instead, because the stored name was no longer in the dialog's catalogue. Nothing said so.

    That is `T199-R1`'s offered-versus-refused disagreement on a new surface, and the fix is the
    same one: the screen and the dialog answer from the same function.
    """
    settings_file = tmp_path / "settings.toml"
    composition = composed(
        settings_file=settings_file,
        ffmpeg_override=tmp_path / "no-ffmpeg-here",
        entry_point=child_probing_then_waiting,
    )
    assert not composition.ffmpeg.available, "this environment has ffmpeg, so it proves nothing"

    names = composition.window._preset_names
    assert names is not None, "composition wired no preset catalogue for the screen"
    offered = names()
    assert offered, "nothing at all was offered, which is not the fix"
    assert presets.AUDIO_MP3.name not in offered, (
        "the screen offers a preset this installation cannot perform, so choosing it as the "
        "default would store a name the next paste does not inherit"
    )

    dialog = composition.window.open_add_dialog()
    try:
        assert set(offered) == {preset.name for preset in dialog.presets}, (
            "the settings screen and the add dialog disagree about the catalogue"
        )
    finally:
        dialog.close()


def test_installing_ffmpeg_widens_the_settings_catalogue_without_a_restart(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """**`T195-R5`.** The catalogue closed over the *startup* ffmpeg report.

    `choose_ffmpeg_location` accepts a new location and updates the report in force, so after
    pointing Settings at a real ffmpeg the add dialog offered four presets — and Settings went on
    offering one, **including after being closed and reopened**, because the lambda behind it read
    the value captured when the application composed. Restart was the only way out, and nothing on
    screen said so.

    Two halves, and the second is the one a naive fix misses: the catalogue has to be right for a
    screen opened *afterwards*, and for one that is **already open** when the location is accepted.
    """
    # **A file this test makes, not the host's ffmpeg** (`T195-R6`). `which("ffmpeg")` made the
    # evidence depend on the machine: with an empty `PATH` the focused set went to two failures and
    # a skip. `an_executable_ffmpeg` is what `T199-R4` wrote for exactly this, and it is executable
    # by the platform's own rule rather than by a mode bit.
    real_ffmpeg = an_executable_ffmpeg(tmp_path, name="ffmpeg-live")

    composition = composed(
        settings_file=tmp_path / "settings.toml",
        ffmpeg_override=tmp_path / "no-ffmpeg-here",
        entry_point=child_probing_then_waiting,
    )
    assert not composition.ffmpeg.available, "this environment started with ffmpeg"

    open_screen = _settings_screen(composition)
    try:
        narrow = open_screen.findChild(QComboBox, DEFAULT_PRESET_NAME)
        assert narrow is not None
        before = narrow.count()

        accept = composition.window._on_ffmpeg_location_chosen
        assert accept is not None
        accept(real_ffmpeg)

        assert narrow.count() > before, (
            "the open Settings screen still offers the catalogue it was built with, so a user who "
            "just installed ffmpeg cannot select the presets it unlocked"
        )
    finally:
        open_screen.close()

    reopened = _settings_screen(composition)
    try:
        combo = reopened.findChild(QComboBox, DEFAULT_PRESET_NAME)
        assert combo is not None
        offered = {combo.itemData(i) for i in range(combo.count())}
        assert presets.AUDIO_MP3.name in offered, (
            "reopening Settings still shows the startup catalogue"
        )
        dialog = composition.window.open_add_dialog()
        try:
            assert offered == {preset.name for preset in dialog.presets}, (
                "Settings and the add dialog disagree about the catalogue after a live change"
            )
        finally:
            dialog.close()
    finally:
        reopened.close()


def test_a_default_set_in_the_preset_manager_reaches_settings_through_composition(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """**The crossing, with nothing carried by hand** (`T-195`, `T195-R4`).

    The UI-level pair proved each screen honours `settings.set_default_preset` — but it moved the
    settings object between them itself, so **deleting composition's `held.settings = settings`
    left both green**. That line is the crossing: without it the manager's write reaches the file
    and the running session never learns of it.

    So this opens the real manager, presses *Set as default*, and then opens the real Settings
    screen out of the same composition. Nothing is handed between them.
    """
    ffmpeg_here = an_executable_ffmpeg(tmp_path)
    settings_file = tmp_path / "settings.toml"
    composition = composed(
        settings_file=settings_file,
        ffmpeg_override=ffmpeg_here,
        entry_point=child_probing_then_waiting,
    )
    chosen = presets.AUDIO_MP3.name

    open_manager = composition.window._manage_presets
    assert open_manager is not None, "composition wired no preset manager"
    manager = open_manager()
    # `manage_presets` is typed `Callable[[], object]` at the window's boundary — the window has no
    # business knowing what screen composition builds. The test does.
    assert isinstance(manager, PresetManager)
    try:
        rows = manager.findChild(QListWidget, PRESET_LIST_NAME)
        assert rows is not None
        for index in range(rows.count()):
            if rows.item(index).data(Qt.ItemDataRole.UserRole) == chosen:
                rows.setCurrentRow(index)
                break
        else:  # pragma: no cover - the catalogue always contains it
            raise AssertionError(f"{chosen} is not in the manager's list")
        button = manager.findChild(QPushButton, SET_DEFAULT_NAME)
        assert button is not None
        button.click()
    finally:
        manager.close()

    screen = _settings_screen(composition)
    try:
        combo = screen.findChild(QComboBox, DEFAULT_PRESET_NAME)
        assert combo is not None
        assert combo.currentData() == chosen, (
            "the Settings screen opened on a different default than the preset manager just set, "
            "so the manager's write never reached the running session"
        )
    finally:
        screen.close()

    # And the session, not only the screen: the next paste inherits it too.
    dialog = composition.window.open_add_dialog()
    try:
        assert dialog._default_preset == chosen
    finally:
        dialog.close()


def test_the_cookies_file_reaches_the_workers_and_never_the_job(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """**`REQ-026` and `DAT-003`'s structural row, from the composed application** (`T-197`).

    Two assertions that have to hold together. The file **does** reach what runs — the manager
    hands it to every child it starts, which is the whole point of the setting — and it **does
    not** reach the job, because `DownloadRequest` has no field for it. The second is what makes
    *"a cookie path this application supplies is never in the database"* structural rather than
    something a filter has to keep catching.
    """
    jar = tmp_path / "cookies.txt"
    jar.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    settings_file = tmp_path / "settings.toml"
    assert (
        core_settings.save(
            core_settings.with_cookie_file(core_settings.Settings(), jar), settings_file
        )
        is None
    )

    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)

    assert composition.manager._cookie_file == jar, (
        "the cookies file never reached the manager, so no worker would ever be signed in"
    )
    # The structural half, asked of the type rather than of an instance: `DownloadRequest` is a
    # slotted frozen dataclass, so its fields are the whole of what a job can carry.
    carried = {field.name for field in dataclasses.fields(DownloadRequest)}
    assert not {name for name in carried if "cookie" in name and "browser" not in name}, (
        f"a job can carry a cookie path — fields are {sorted(carried)}. DAT-003's first row is "
        "structural only while the model cannot hold the value"
    )


def test_changing_the_cookies_file_reaches_jobs_already_queued(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """**The late binding the maintainer ruled deliberate**, asserted rather than left implied.

    A queued job cannot carry the path — that is the guarantee — so it authenticates with whatever
    file is set when its worker *starts*. `DAT-003`'s 2026-08-10 amendment states the consequence
    plainly because it is a surprise otherwise: changing or clearing the file changes
    authentication for everything already queued and not yet started.

    This is the assertion that would fail if someone later made the path per-job to "fix" the
    surprise — which would put it back in the model and reopen the decision.
    """
    first = tmp_path / "first-cookies.txt"
    first.write_text("# Netscape HTTP Cookie File\n# first\n", encoding="utf-8")
    second = tmp_path / "second-cookies.txt"
    second.write_text("# Netscape HTTP Cookie File\n# second\n", encoding="utf-8")
    settings_file = tmp_path / "settings.toml"
    assert (
        core_settings.save(
            core_settings.with_cookie_file(core_settings.Settings(), first), settings_file
        )
        is None
    )

    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)
    assert composition.manager._cookie_file == first

    write_cookies = composition.window._on_cookie_file_chosen
    assert write_cookies is not None, "composition wired no cookies writer"
    write_cookies(second)
    QApplication.processEvents()

    assert composition.manager._cookie_file == second, (
        "a job that starts from now on would still use the old cookies file"
    )
    assert core_settings.load(settings_file).settings.cookie_file == second

    write_cookies(None)
    QApplication.processEvents()
    assert composition.manager._cookie_file is None, (
        "clearing the file left workers signed in, which is the opposite of what was asked"
    )


def test_an_unusable_cookies_file_is_refused_and_changes_nothing(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """`ARC-008`, and `T-197`'s own criterion about the quiet failure.

    A cookies file that is missing must **report** rather than downloading unauthenticated, which
    looks like a paywall bypass failing silently — `REQ-EXCL-002` is emphatic that this feature is
    for content the user already has access to, so failing to authenticate is a thing to say out
    loud. Refused rather than stored, on the contract `T199-R3` settled for the ffmpeg location.
    """
    good = tmp_path / "cookies.txt"
    good.write_text("# Netscape HTTP Cookie File\n# good\n", encoding="utf-8")
    settings_file = tmp_path / "settings.toml"
    assert (
        core_settings.save(
            core_settings.with_cookie_file(core_settings.Settings(), good), settings_file
        )
        is None
    )
    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)

    write_cookies = composition.window._on_cookie_file_chosen
    assert write_cookies is not None
    write_cookies(tmp_path / "gone" / "cookies.txt")
    QApplication.processEvents()

    assert composition.manager._cookie_file == good, (
        "a refused cookies file changed what workers receive"
    )
    assert core_settings.load(settings_file).settings.cookie_file == good, (
        "a refused cookies file was persisted"
    )
    assert "not be authenticated" in composition.window.statusBar().currentMessage(), (
        "the refusal was silent, so the user would download unauthenticated without being told"
    )


def test_an_unusable_cookie_path_does_not_reach_the_log_that_reports_it(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """**`T197-R1`, the half that leaked after the first correction.**

    Registering the *accepted* path protected the ordinary case and missed the reported one: an
    unusable value is discarded from the settings, its text goes into `problem.reason`, and
    composition **logs that reason**. So the path most certain to be written was the one nothing
    had registered — and the review reproduced `/home/alice/session.txt` arriving in the log by
    that exact route.

    `load()` now carries every literal it read as data, valid or not, and composition registers
    them before it writes anything. Asserted by capturing what this application's own handlers
    emit for the reason, rather than by reading the ordering.
    """
    # **Outside `tmp_path`, and that is not fussiness.** pytest names its temp directory after the
    # test, so a jar under it sat at `.../test_an_unusable_cookie_path_d0/session.txt` — the word
    # *cookie* in the directory, put there by the test's own name, matched the shape rule and
    # redacted the path for the wrong reason. The first version of this test passed with the
    # registration deleted. That is the `cookies.*` fixture mistake again, one level up.
    neutral = Path(tempfile.mkdtemp())
    named_like_nothing = neutral / "session.txt"
    settings_file = tmp_path / "settings.toml"
    settings_file.write_text(
        f"[cookies]\nfile = {json.dumps(str(named_like_nothing))}\n", encoding="utf-8"
    )

    # Proved to be invisible to the shape rules *before* composing, so what is measured below is
    # the registration and nothing else.
    app_logging.forget_the_secrets()
    assert str(named_like_nothing) in app_logging.redact(f"see {named_like_nothing}"), (
        "this path is already redacted by shape, so it cannot show what registering buys"
    )

    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)
    assert composition.window is not None

    read = core_settings.load(settings_file)
    assert read.settings.cookie_file is None, "an absent jar was accepted"
    assert read.problem is not None
    assert str(named_like_nothing) in read.problem.reason, (
        "the dialog must name the file the user set — it is their value, shown to them"
    )

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(app_logging.RedactingFormatter(app_logging.LOG_FORMAT))
    log = logging.getLogger("tracksandtrails.cookie-leak-probe")
    log.handlers = [handler]
    log.propagate = False
    log.warning("settings: %s", read.problem.reason)

    assert str(named_like_nothing) not in stream.getvalue(), (
        f"the cookie path reached a log through the ARC-008 report:\n{stream.getvalue()}"
    )
    assert "does not exist" in stream.getvalue(), "the report was scrubbed rather than the path"


def test_choosing_no_cookies_on_the_real_screen_clears_the_browser_everywhere(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """**The review's evidence note, taken**: the widget-level test stops at the dialog's own
    methods and would stay green with the composition wiring gone. This drives the real loop —
    screen radio → composition → settings file → window → screen — on the composed application.
    """
    settings_file = tmp_path / "settings.toml"
    assert (
        core_settings.save(
            core_settings.with_cookie_browser(core_settings.Settings(), "firefox:Work"),
            settings_file,
        )
        is None
    )
    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)

    screen = composition.window.open_settings()
    assert screen is not None
    try:
        browser_radio = screen.findChild(QRadioButton, "cookieSourceBrowser")
        none_radio = screen.findChild(QRadioButton, "cookieSourceNone")
        assert browser_radio is not None and none_radio is not None
        assert browser_radio.isChecked(), "the stored browser source never reached the screen"

        none_radio.click()
        QApplication.processEvents()

        read = core_settings.load(settings_file)
        assert read.settings.cookie_browser is None, "No cookies did not clear the stored browser"
        assert read.settings.cookie_file is None
        assert none_radio.isChecked() and not browser_radio.isChecked(), (
            "the screen still claims a cookie source after the user chose none"
        )
        assert composition.window._cookie_browser is None, (
            "the window still holds the browser, so the next screen would reopen showing it"
        )
    finally:
        screen.close()
        QApplication.processEvents()


def test_retargeting_through_the_window_keeps_the_jobs_cookie_binding(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """**The evidence note's other half**: `with_connection_of` was proven in isolation, and
    nothing proved `_retarget_job` actually calls it. This retargets a real queued job through the
    window's own handler and reads the store back.
    """
    database = tmp_path / "retarget.sqlite3"
    connection = db.connect(database)
    repository = JobRepository(connection)
    bound = DownloadRequest(
        url="https://example.invalid/bound",
        output_directory=str(tmp_path / "downloads"),
        format_selector="bestvideo+bestaudio/best",
        output_template="%(title)s.%(ext)s",
        cookies_from_browser="firefox:Work",
    )
    repository.append([Job(id="bound-1", url=bound.url, request=bound, queue_position=0)])
    connection.close()

    composition = composed(database=database, entry_point=child_probing_then_waiting)
    assert spin(lambda: shown_status(composition, "bound-1") is not None, timeout=30)

    composition.window._retarget_job("bound-1", "Audio only (MP3)")
    assert spin(
        lambda: (
            (job := composition.store.get("bound-1")) is not None
            and job.request.media_kind is not bound.media_kind
        ),
        timeout=60,
    ), "the retarget never landed, so this proves nothing about what it preserved"

    after = composition.store.get("bound-1")
    assert after is not None
    assert after.request.cookies_from_browser == "firefox:Work", (
        "retargeting through the window dropped the browser the job was bound to at queue time"
    )


def test_pointing_settings_at_ffmpeg_reaches_the_preset_manager(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
    qapp: QApplication,
) -> None:
    """**`T-226`.** The manager was built with the *startup* ffmpeg answer.

    `T195-R5` fixed this for the add dialog's catalogue and the settings screen; `manage_presets`
    still passed `ffmpeg.available` — the value composition closed over — so a user who started
    without ffmpeg, installed one and pointed Settings at it went on being told by *this* screen
    that its ffmpeg-dependent presets would fail. Restart was the only way out and nothing said so.

    Opened through the route the footer button takes, and the **inverse transition is asserted
    first**: a manager opened before the location is accepted must still carry the warning, or the
    positive half would pass with the reason deleted.
    """
    real_ffmpeg = an_executable_ffmpeg(tmp_path, name="ffmpeg-live")
    composition = composed(
        settings_file=tmp_path / "settings.toml",
        ffmpeg_override=tmp_path / "no-ffmpeg-here",
        entry_point=child_probing_then_waiting,
    )
    assert not composition.ffmpeg.available, "this environment started with ffmpeg"

    needs_it = next(p for p in presets.BUILT_IN_PRESETS if composition.manager.requires_ffmpeg(p))

    def manager_reason() -> str:
        opener = composition.window._manage_presets
        assert opener is not None, "composition wired no preset manager"
        screen = opener()
        assert isinstance(screen, PresetManager), "the manager route returned no screen"
        qapp.processEvents()
        try:
            listing = screen.findChild(QListWidget, PRESET_LIST_NAME)
            assert listing is not None
            for row in range(listing.count()):
                # The list decorates each name — 'Audio only (MP3) - built-in' - so
                # the match is on the name it starts with, not on the whole label.
                if listing.item(row).text().startswith(needs_it.name):
                    listing.setCurrentRow(row)
                    break
            else:
                raise AssertionError(
                    f"{needs_it.name} is not in the manager's list: "
                    f"{[listing.item(i).text() for i in range(listing.count())]}"
                )
            qapp.processEvents()
            return screen._reason.text()
        finally:
            screen.close()
            qapp.processEvents()

    assert NO_FFMPEG_REASON in manager_reason(), (
        "the manager did not warn about an ffmpeg-dependent preset while ffmpeg is absent, so the "
        "positive half below would prove nothing"
    )

    accept = composition.window._on_ffmpeg_location_chosen
    assert accept is not None
    accept(real_ffmpeg)

    assert NO_FFMPEG_REASON not in manager_reason(), (
        "the Preset Manager still says this preset will fail for want of ffmpeg, after Settings "
        "accepted a real one — it was built with the startup answer (T-226)"
    )


# --- network options (T-196) ----------------------------------------------------------------


def test_the_stored_network_options_reach_the_screen_and_the_next_request(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """**`T-196`'s first criterion, through `compose` rather than through the units.**

    Two halves that have to hold together, and each has been the broken one on this surface
    before: the Settings screen opens on the stored value (`T195-R5`), and the value a *request*
    inherits is the one in force (`T-075`, `T195-R1`). A test that asserted only the store would
    be the shape `T-109` was submitted with.
    """
    settings_file = tmp_path / "settings.toml"
    stored = NetworkOptions(proxy="http://proxy.invalid:8080", rate_limit_bytes=8192, retries=2)
    assert (
        core_settings.save(
            core_settings.with_network_options(core_settings.Settings(), stored), settings_file
        )
        is None
    )

    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)

    read_default = composition.window._default_network
    assert read_default is not None, "composition wired nothing for a new request to inherit"
    assert read_default() == stored

    screen = _settings_screen(composition)
    try:
        proxy = screen.findChild(QLineEdit, PROXY_NAME)
        rate = screen.findChild(QSpinBox, RATE_LIMIT_NAME)
        retries = screen.findChild(QSpinBox, RETRIES_NAME)
        assert proxy is not None and rate is not None and retries is not None
        assert proxy.text() == "http://proxy.invalid:8080"
        assert rate.value() == 8, "the stored limit is not what the screen opened on"
        assert retries.value() == 2
    finally:
        screen.close()
        QApplication.processEvents()


def test_a_network_option_chosen_on_the_screen_is_applied_and_saved(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """Applied *and* saved, in that order, and neither is optional (`choose_concurrency`'s rule).

    Applying without saving makes the setting forget itself at the next launch; saving without
    applying makes it appear to do nothing until a restart, which is `T-075`. Driven through the
    screen's own control, so what is asserted is the route a user takes.
    """
    settings_file = tmp_path / "settings.toml"
    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)

    screen = _settings_screen(composition)
    try:
        retries = screen.findChild(QSpinBox, RETRIES_NAME)
        assert retries is not None
        retries.setValue(0)
        QApplication.processEvents()
    finally:
        screen.close()
        QApplication.processEvents()

    read_default = composition.window._default_network
    assert read_default is not None
    assert read_default().retries == 0, (
        "the next request would still inherit the downloader's own retry count"
    )
    assert core_settings.load(settings_file).settings.network.retries == 0, (
        "the choice was applied to this session only"
    )


def test_a_stored_proxy_is_redacted_by_the_assembled_application(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """**`T-196`'s third criterion**, asked of the sink rather than of the intention.

    A proxy is the one `REQ-023` setting that can carry a credential, and `settings.toml` is a new
    place for it to live. `redact`'s shape rules take the *userinfo* out of a bare
    `user:pass@host` and leave the address — and yt-dlp's own verbose output names the proxy in
    full — so the literal is registered, exactly as a cookie path is.

    Through `compose`, for `test_a_short_cookie_path_is_redacted_by_the_assembled_application`'s
    reason: a unit test that registered the value itself would agree with the intended wiring
    rather than read the real one, which is this project's most-recorded defect.
    """
    settings_file = tmp_path / "settings.toml"
    settings_file.write_text(
        '[network]\nproxy = "http://me:hunter2@proxy.invalid:8080"\n', encoding="utf-8"
    )

    # The refused value, which is the one `T197-R1` found leaking: it is discarded from the
    # settings and its text goes into the `ARC-008` reason composition logs.
    refused = "http://me:hunter2@proxy.invalid:8080"
    line = f"settings: could not use {refused}"

    app_logging.forget_the_secrets()
    try:
        # **The assertion has to be about the host, and this is why** (`T197-R1`'s own trap, which
        # this test fell into once: a mutation removing the registration left it green). `redact`'s
        # URL rule already takes the *userinfo* out of a well-formed URL, so asserting that the
        # whole literal is absent proves only that the password went — which happens with nothing
        # registered at all. What registering buys is the address, and the sanity check below is
        # what makes the assertion after it mean something.
        assert "proxy.invalid" in app_logging.redact(line), (
            "the shape rules already remove the address, so this test cannot show what "
            "registering the literal buys"
        )

        composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)

        assert "proxy.invalid" not in app_logging.redact(line), (
            f"a refused proxy survived redaction: {app_logging.redact(line)!r}"
        )
        assert composition.window._default_network is not None
        assert composition.window._default_network().proxy is None, "it was refused and stored"
    finally:
        app_logging.forget_the_secrets()


def test_a_proxy_chosen_at_runtime_is_redacted_too(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
) -> None:
    """The second route into the same leak, and it needs its own test (`T197-R1`'s lesson).

    A proxy arrives two ways — read from `settings.toml` at startup, and typed into the screen
    while the application runs — through different code. A mutation reverting only one of them
    left every existing test green when this happened to the cookie path, twice.
    """
    settings_file = tmp_path / "settings.toml"
    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)

    app_logging.forget_the_secrets()
    try:
        screen = _settings_screen(composition)
        try:
            proxy = screen.findChild(QLineEdit, PROXY_NAME)
            assert proxy is not None
            proxy.setText("http://proxy.invalid:8080")
            QApplication.processEvents()
        finally:
            screen.close()
            QApplication.processEvents()

        line = "yt-dlp: Proxy map: {'all': 'http://proxy.invalid:8080'}"
        assert "proxy.invalid:8080" not in app_logging.redact(line), (
            f"a proxy chosen at runtime was not registered: {app_logging.redact(line)!r}"
        )
    finally:
        app_logging.forget_the_secrets()


def test_a_proxy_and_a_rate_limit_set_on_the_screen_reach_the_options_yt_dlp_gets(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """**`T196-R4`.** The whole crossing, in one regression: screen → file → request → options.

    The gate this task claimed was false-green. A reviewer mutation that kept only the retry count
    in `choose_network` — dropping every live proxy and rate-limit choice — passed every focused
    composition test: the one live apply/save test changed only retries, the startup tests read
    already-stored values, and the runtime-proxy test proved registration alone.

    So this ends where the criterion says it ends — *"asserted through the options the adapter
    builds, not against the stored value"* — and it starts at the two controls a user touches.
    """
    settings_file = tmp_path / "settings.toml"
    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)

    screen = _settings_screen(composition)
    try:
        proxy = screen.findChild(QLineEdit, PROXY_NAME)
        rate = screen.findChild(QSpinBox, RATE_LIMIT_NAME)
        assert proxy is not None and rate is not None
        QTest.keyClicks(proxy, "http://proxy.invalid:8080")
        QTest.keyClick(proxy, Qt.Key.Key_Return)
        rate.setValue(512)
        QApplication.processEvents()
    finally:
        screen.close()
        QApplication.processEvents()

    stored = core_settings.load(settings_file).settings.network
    assert stored.proxy == "http://proxy.invalid:8080", f"the proxy was not persisted: {stored}"
    assert stored.rate_limit_bytes == 512 * 1024, f"the rate limit was not persisted: {stored}"

    dialog = composition.window.open_add_dialog()
    assert dialog is not None
    try:
        type_urls(dialog, "https://composed.invalid/network-options")
        dialog.resolve()
        assert spin(lambda: bool(dialog.rows) and dialog.rows[0].committable, timeout=60), (
            f"the URL never resolved: {dialog.status_text()}"
        )
        # The dialog's own single request builder — the one every committed job goes through
        # (`T-075`, `UX-004`) — rather than a second construction this test invented.
        built = dialog._request_for(dialog.rows[0])
    finally:
        dialog.close()
        QApplication.processEvents()

    assert built.proxy == "http://proxy.invalid:8080", (
        f"a job built after the choice carries {built.proxy!r}: the setting is stored and does "
        "not run, which is T-075's shape"
    )
    assert built.rate_limit_bytes == 512 * 1024

    options = adapter.build_options(built, "o.%(ext)s")
    assert options["proxy"] == "http://proxy.invalid:8080"
    assert options["ratelimit"] == 512 * 1024


def test_no_keystroke_of_a_credentialed_proxy_reaches_the_file_or_a_job(
    composed: Callable[..., application.Composition],
    spin: Callable[..., bool],
    tmp_path: Path,
) -> None:
    """**`T196-R1`, Critical, on the composed application and through the real keyboard.**

    Typing `http://alice:12345@proxy.invalid:8080` passes through `http://alice:12345`, which is a
    legal `scheme://host:port` — a numeric password is indistinguishable from a port, so no
    grammar can refuse it. The screen used to write every accepted keystroke, so composition
    applied and **saved** that prefix, and the next queued request would have carried it into the
    jobs row. Asserted in all three places the credential could have come to rest.
    """
    settings_file = tmp_path / "settings.toml"
    composition = composed(settings_file=settings_file, entry_point=child_probing_then_waiting)

    screen = _settings_screen(composition)
    try:
        proxy = screen.findChild(QLineEdit, PROXY_NAME)
        assert proxy is not None
        QTest.keyClicks(proxy, "http://alice:12345@proxy.invalid:8080")
        QTest.keyClick(proxy, Qt.Key.Key_Return)
        QApplication.processEvents()
    finally:
        screen.close()
        QApplication.processEvents()

    in_memory = composition.window._default_network
    assert in_memory is not None
    assert in_memory().proxy is None, f"a credential is in force in memory: {in_memory().proxy!r}"

    on_disk = settings_file.read_text(encoding="utf-8") if settings_file.exists() else ""
    assert "alice" not in on_disk and "12345" not in on_disk, (
        f"a credential reached settings.toml:\n{on_disk}"
    )

    dialog = composition.window.open_add_dialog()
    assert dialog is not None
    try:
        type_urls(dialog, "https://composed.invalid/no-credential")
        dialog.resolve()
        assert spin(lambda: bool(dialog.rows) and dialog.rows[0].committable, timeout=60), (
            f"the URL never resolved: {dialog.status_text()}"
        )
        built = dialog._request_for(dialog.rows[0])
    finally:
        dialog.close()
        QApplication.processEvents()

    assert built.proxy is None, f"a queued request carries {built.proxy!r}"


@pytest.mark.parametrize(
    ("stored", "redacted"),
    [
        ("http://proxy.invalid:8080", True),
        ("http://alice:hunter2@proxy.invalid:8080", True),
        ("http://", False),
        ("localhost", False),
    ],
)
def test_what_a_stored_proxy_costs_the_log_is_bounded_at_both_ends(
    composed: Callable[..., application.Composition],
    tmp_path: Path,
    stored: str,
    redacted: bool,
) -> None:
    """**`T196-R2`, through the composed application and the real formatter.**

    Two failures, in opposite directions, from one classifier that keyed on `://` or `@`:

    - `proxy = "http://"` was **registered**, so an ordinary `http://other.invalid/x` in any later
      line came back as `<redacted>other.invalid/x` — the log damaged by the machinery meant to
      protect it, which is `T197-R6` in the other direction.
    - `proxy = "localhost"` was **not** registered while the `ARC-008` reason still quoted it, so
      the value reached the log through the sentence written to keep it out.

    Both halves are asserted for every shape: the value is gone when it could leak, and ordinary
    content stays legible when it could not.
    """
    settings_file = tmp_path / "settings.toml"
    settings_file.write_text(f'[network]\nproxy = "{stored}"\n', encoding="utf-8")

    app_logging.forget_the_secrets()
    try:
        composed(settings_file=settings_file, entry_point=child_probing_then_waiting)

        # The two lines a stored proxy can actually reach: the `ARC-008` reason composition logs
        # — read from `load()`, which is where composition gets the string it logs — and yt-dlp's
        # own verbose dump, which names the proxy in full.
        problem = core_settings.load(settings_file).problem
        if problem is None:
            assert redacted and stored == "http://proxy.invalid:8080", (
                f"{stored!r} was accepted without a report and should not have been"
            )
        else:
            assert stored not in app_logging.redact(problem.reason), (
                f"the settings report names the refused proxy: "
                f"{app_logging.redact(problem.reason)!r}"
            )
        if redacted:
            yt_dlp_line = f"yt-dlp: Proxy map: {{'all': '{stored}'}}"
            assert stored not in app_logging.redact(yt_dlp_line), (
                f"a proxy that could reach a log survives the formatter: "
                f"{app_logging.redact(yt_dlp_line)!r}"
            )

        # And the other direction, which is the half that has no natural alarm: ordinary content
        # must stay readable. `http://other.invalid/x` shares its prefix with one of the values
        # above, and `localhost` is an ordinary word in a diagnostic.
        ordinary = "downloading http://other.invalid/x through localhost"
        assert app_logging.redact(ordinary) == ordinary, (
            f"registering {stored!r} damaged an unrelated line: {app_logging.redact(ordinary)!r}"
        )
    finally:
        app_logging.forget_the_secrets()


def test_a_newer_database_stops_composition_rather_than_opening_it(
    composed: Callable[..., application.Composition], tmp_path: Path
) -> None:
    """`T-320`: the refusal has to reach the startup path, not only `persistence/db`.

    `compose()` opens the database and then **recovers interrupted jobs on the very next line**,
    rewriting rows. So a database from a newer build has to stop composition outright — before
    recovery touches a schema this build does not understand, and before a window exists to show
    a queue read through the wrong columns.

    `run()` turns this into a message box and exit 4. That last hop is inside the uncovered region
    `present()`'s docstring names: `run()` builds its own `QApplication` and cannot be called from
    a session that already has one.
    """
    database = tmp_path / "from_the_future.db"
    connection = db.connect(database)
    connection.execute(f"PRAGMA user_version = {db.latest_version() + 1:d}")
    connection.commit()
    connection.close()

    with pytest.raises(db.NewerSchemaError):
        composed(database=database)
