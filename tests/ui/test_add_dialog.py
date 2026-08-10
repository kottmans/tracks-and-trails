"""The add-URL dialog as a staging list (`T-118`, `UX-003`), on `T-016`'s foundations.

`UX-003`: nothing enters the queue unprobed. Pasting resolves every line, and *Add to queue*
commits only what resolved. The state machine underneath is `ui/staging.py` and is tested without
a `QApplication` in `tests/unit/test_staging.py`; what is asserted here is what the **widget** does
with it.

**Every finding this dialog has ever taken is a constraint on the rewrite, not history.**
`T016-R1` (a result belongs to a URL, not a job id), `T016-R2` (closing abandons), `T016-R3`
(nothing blocks the GUI thread), `T016-R6` (untrusted text is plain), `T-075` (the request that
runs is the one selected at Add) and `T115-R1` (one ordered admission) all have tests below, and
each of them describes a defect that shipped once.

**The process boundary is not mocked** (`ai/TESTING.md` §6). Every probe below spawns a real
process over a real `multiprocessing.Queue`; what the child *is* varies, exactly as in
`tests/integration/test_manager.py` — a child replaying a recorded fixture, a child that fails
with recorded text, a child that never answers, and a child that answers only when told to.

What *is* faked is the network: fixtures instead of sites (`ai/TESTING.md` §1), and an injected
`ThumbnailLoader` over bytes already in this repository. Qt still decodes the pixmap for real.
The **shipping** loader's failure path is exercised too (`T016-R5`), against a local URL that
cannot resolve — a loader that can only succeed cannot prove what happens when one does not.

Persistence is real where the claim is about persistence. `FakeSink` is a zero-latency stand-in
for the tests that are about the dialog's logic; the `ARC-005` tests drive the concrete
`QueueWriter` over a real SQLite file, under a genuinely held writer lock (`T016-R3`).

The dialog is driven through its **object names** rather than accessors added for the suite.
"""

import json
import statistics
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, Final

import pytest
from PySide6.QtCore import (
    QEvent,
    QItemSelectionModel,
    QModelIndex,
    QPoint,
    QPointF,
    QRect,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QFont,
    QFontMetrics,
    QImage,
    QPainter,
    QWheelEvent,
)
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractItemDelegate,
    QApplication,
    QComboBox,
    QDialog,
    QLabel,
    QListView,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStyleOptionViewItem,
    QWidget,
)

from tests.qt_lifecycle import drain
from tracks_and_trails.core import presets as preset_registry
from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import (
    DownloadRequest,
    FormatInfo,
    Job,
    MediaInfo,
    MediaKind,
    PlaylistEntry,
    Preset,
)
from tracks_and_trails.core.paths import MAX_COMPONENT_BYTES, contained_output_path
from tracks_and_trails.downloader import ytdlp_adapter as adapter
from tracks_and_trails.downloader.manager import (
    DEFAULT_PROBE_CONCURRENCY,
    DownloadManager,
)
from tracks_and_trails.downloader.protocol import (
    Failed,
    Probed,
    Progress,
    SessionKind,
    Stage,
    WorkerFinished,
)
from tracks_and_trails.ui.add_dialog import (
    STATE_TEXT,
    UNKNOWN_TEXT,
    AddUrlDialog,
    FormatPanel,
    describe_kind,
    format_duration,
    headline_text,
    row_text,
    selector_candidates,
    split_urls,
)
from tracks_and_trails.ui.playlist_selection import PlaylistSelection
from tracks_and_trails.ui.row_delegate import (
    CHOOSE_FORMATS_DATA,
    CHOOSE_FORMATS_TEXT,
    EDIT_HINT,
    EDITOR_WIDTH,
    EXPANDED_ROLE,
    GAP,
    HEADLINE_ROLE,
    INHERITED_TEXT,
    MANAGE_PRESETS_DATA,
    MANAGE_PRESETS_TEXT,
    MENU_ZONE_WIDTH,
    OPTIONS_DATA,
    OPTIONS_TEXT,
    PADDING,
    PRESET_CHOICES_ROLE,
    PRESET_ROLE,
    ROW_HEIGHT,
    ROW_PRESET_NAME,
    SELECTOR_LINES,
    SELECTOR_ROLE,
    STATE_ROLE,
    TEMPLATE_AVAILABLE_ROLE,
    TEMPLATE_DATA,
    TEMPLATE_TEXT,
    VERBS_ROLE,
    RowDelegate,
    selector_line_width,
)
from tracks_and_trails.ui.staging import SETTLED, Row, RowState
from tracks_and_trails.ui.thumbnails import THUMBNAIL_SIZE

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
INFODICTS: Final = REPO_ROOT / "tests" / "fixtures" / "infodicts"
ERRORS: Final = REPO_ROOT / "tests" / "fixtures" / "errors"

#: A real image already in this repository, used as thumbnail bytes. Reusing the application icon
#: rather than committing a second PNG: the claim is that Qt decoded *something* into a pixmap.
THUMBNAIL_SOURCE: Final = (
    REPO_ROOT / "src" / "tracks_and_trails" / "resources" / "icons" / "icon.png"
)

#: **The absolute budget, sized for headroom rather than for the measurement** (`T118-R10`).
#:
#: `NFR-001` budgets ~100 ms for an interaction. A paste of `SUPPORTED_PASTE` measures **0.042 s**
#: on the development machine (2026-08-03, delegate build), so this is a **24x margin** — and it is
#: deliberately not the 0.5 s the widget-per-row design needed, because that figure was the largest
#: one Linux measurement would bear and it is exactly what made `T118-R10` pass on one hosted
#: Windows run and fail on another with nothing changed between them.
#:
#: The property this can still catch is a return to cost that grows with the paste: the design it
#: replaced would spend seconds here, not milliseconds. **This absolute bound is the gate**, and it
#: is the only timing claim in this module that a runner is asked to hold. `SCALING_HEADROOM`'s
#: ratio is *diagnostic*: transient load moves it, for the reasons recorded on that constant
#: (`T118-R17`, `T-122`), so it reports rather than gates.
INTERACTION_BUDGET_SECONDS: Final = 1.0

#: The paste size the design supports, and the size the budget is asserted at.
#:
#: **Five hundred, which is what the ceiling was hiding.** Every row used to carry its own format
#: control widget (`UX-004`), costing ~86 ms at a hundred and fifty on a developer machine and
#: 0.722 s on hosted Windows — so this constant was pinned at 150 and recorded as a real limit
#: rather than a weakened test. `T-119`'s delegate builds one editor for the row being edited, so
#: the limit is gone: measured 0.020 s at 125, 0.042 s at 500 and 0.047 s at 1000.
SUPPORTED_PASTE: Final = 500

#: A quarter-size paste, for the scaling comparison below.
SMALL_PASTE: Final = SUPPORTED_PASTE // 4

#: How much more a paste four times the size may cost. Four would be exactly linear; this allows
#: it to be somewhat worse than linear while still failing hard on the quadratic-ish growth a
#: widget per row produces.
#:
#: **A ratio does not cancel runner speed** (`T118-R17`, `T-122`). The previous version of this
#: constant claimed it did — "two measurements taken moments apart on one machine share its speed,
#: so a slow runner slows both sides and cancels out". That is true of a *sustained* speed
#: difference and false of a *transient* one, and the denominator here is tens of milliseconds, so
#: any absolute perturbation is amplified enormously. Hosted Windows measured 0.0321 s and
#: 1.4935 s in run `30859578131` — a factor of 46.5 — while the separate absolute-budget test did
#: the identical 500-row resolve *under* 1.0 s minutes apart, and `STARBASE` passed both.
#:
#: What makes the comparison usable is the estimator, not the arithmetic: see `SCALING_PAIRS` and
#: `superlinear_growth`.
SCALING_HEADROOM: Final = 6.0

#: How many interleaved small/large pairs the scaling gate measures.
#:
#: **Three, and interleaved, so one stall cannot decide the outcome.** A stall lands in one sample;
#: the median of three ignores it entirely. Interleaving matters as much as repeating — measuring
#: all the small ones first and all the large ones second lets a stall that begins midway through
#: land wholly on one side, which is precisely the shape that produced the 46.5.
SCALING_PAIRS: Final = 3

SINGLE_ITEM: Final = "archive_org_big_buck_bunny"
PLAYLIST: Final = "archive_org_art_of_war_playlist"
AUDIO_ONLY: Final = "archive_org_test_mp3"

#: The complete keyboard order `NFR-005` requires, **transcribed by hand** (`T016-R4`).
#:
#: Two corrections live in this one constant. The first version of the test derived it from
#: `AddUrlDialog.focus_chain()` — the list the dialog feeds to Qt — so it proved only that the
#: list equalled itself, and a mutation reversing two entries survived. The second version was
#: independent but named only the editor, buttons and preset, and *filtered every other focusable
#: node out of its own observation*; six selectable result and status labels were reachable by
#: keyboard, landed after Close, and gated nothing. This names all twelve.
EXPECTED_TAB_ORDER: Final = (
    "urlInput",
    "retryFailedButton",
    # `T-203`'s verb bar sat here until `UX-011` moved its verbs into the row's menu — real
    # `QAction`s reached through the list itself, so the chain holds nothing separate for them.
    "stagingList",
    # Selectable, therefore focusable, therefore declared (`T016-R4`).
    "statusMessage",
    "presetChoice",
    # `T-076`. Placed with the preset it qualifies rather than at the end: a user who has just
    # chosen "Audio only (MP3)" is one Tab away from the bitrate that preset will convert at.
    "audioBitrateChoice",
    "selectorValue",
    # `UX-009` moved *Manage presets…* off the row and into the footer. `ResetRole` places it at the
    # **left** of the button box, and the keyboard follows the eye — `T-200`'s rule that tab order
    # matches visual order — so it is reached before the two buttons that decide the dialog.
    "managePresetsButton",
    "addButton",
    "closeButton",
)


# --- the recorded fixtures, read the same way here and in the spawned child -------------------


def load_info(name: str) -> dict[str, Any]:
    """One recorded `info_dict`, as `T-018` committed it."""
    data = json.loads((INFODICTS / f"{name}.json").read_text(encoding="utf-8"))
    return dict(data["info_dict"])


def load_error(name: str) -> dict[str, Any]:
    data = json.loads((ERRORS / f"{name}.json").read_text(encoding="utf-8"))
    return dict(data["error"])


def fixture_url(name: str) -> str:
    """The URL a fixture describes, which is what a test pastes into the dialog."""
    info = load_info(name)
    url = info.get("webpage_url") or info.get("original_url") or info.get("url")
    assert isinstance(url, str) and url, f"{name} records no URL to probe"
    return url


def _fixture_for(url: str) -> dict[str, Any]:
    for path in sorted(INFODICTS.glob("*.json")):
        info = load_info(path.stem)
        if url in (info.get("webpage_url"), info.get("original_url"), info.get("url")):
            return info
    raise LookupError(f"no recorded fixture describes {url!r}")


# --- the children -----------------------------------------------------------------------------
#
# Module level and picklable by reference: `spawn` imports this module in the child and looks the
# function up by name, so a closure or a local would not survive the boundary.


def child_replaying_a_fixture(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """Probe from a recorded fixture; download by starting and not stopping.

    Kind-aware because `SessionValidator` is: `Probed` is not a legal outcome for a download
    session, so a child that sent one regardless would fail the job it was meant to be running.
    """
    if kind is SessionKind.PROBE:
        from tracks_and_trails.downloader.ytdlp_adapter import project_media

        try:
            info = _fixture_for(request.url)
        except LookupError:
            # **A URL with no fixture never answers**, rather than dying. A child that exits
            # ends its session and returns the manager to idle, which silently satisfied
            # `test_a_later_dialog_can_still_probe_after_one_is_closed_mid_probe` even with the
            # `T016-R2` fix reverted — the mutation survived because the worker died on its own.
            while True:
                time.sleep(0.05)
        queue.put(Probed(job_id=job_id, media=project_media(info)))
        queue.put(WorkerFinished(job_id=job_id, exit_code=0))
        return

    queue.put(Progress(job_id=job_id, stage=Stage.DOWNLOADING_VIDEO, downloaded_bytes=1))
    while True:
        time.sleep(0.05)


def child_replaying_or_failing(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """Resolve a URL with a recorded fixture, and fail one without.

    **A mixed batch is the only shape that tests the commit filter.** A batch where everything
    fails passes whether or not the filter works, because `retarget` refuses a `FAILED` job and
    the whole commit aborts downstream — a guard resting on another guard, which is `T081-R4`.
    """
    from tracks_and_trails.downloader.ytdlp_adapter import project_media

    try:
        info = _fixture_for(request.url)
    except LookupError:
        error = load_error("unsupported_url")
        queue.put(
            Failed(job_id=job_id, kind=ErrorKind(error["expected_kind"]), message=error["message"])
        )
        queue.put(WorkerFinished(job_id=job_id, exit_code=1))
        return
    queue.put(Probed(job_id=job_id, media=project_media(info)))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))


def child_probing_a_markup_title(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """A site whose title and uploader look like HTML (`T016-R6`).

    Not hypothetical: a title is arbitrary text chosen by whoever uploaded the item, and `<b>` is
    two keystrokes. What matters is that the dialog shows it rather than interpreting it.
    """
    media = MediaInfo(
        url=request.url,
        title="<b>VISIBLE</b>",
        uploader="<i>uploader</i>",
        duration_seconds=61.0,
    )
    queue.put(Probed(job_id=job_id, media=media))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))


def child_failing_as_recorded(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """Fail with the extractor's own recorded words (`REQ-005`, `NFR-006`)."""
    error = load_error("unsupported_url")
    queue.put(
        Failed(job_id=job_id, kind=ErrorKind(error["expected_kind"]), message=error["message"])
    )
    queue.put(WorkerFinished(job_id=job_id, exit_code=1))


def child_never_returning(
    kind: SessionKind, job_id: str, request: DownloadRequest, queue: Any, **_: Any
) -> None:
    """A session that never answers. The only thing that can prove cancellation works."""
    while True:
        time.sleep(0.05)


# --- the queue the dialog writes into ---------------------------------------------------------


class FakeStore:
    """An in-memory `JobStore` for the manager, and the rows `FakeSink` writes into."""

    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.writes: list[tuple[str, JobStatus]] = []
        #: Ids deleted, in order (`T-118`): what the dialog withdrew rather than committed.
        self.removals: list[str] = []
        #: Hold write callbacks instead of running them, so an ordering rule can be observed.
        self.defer_updates = False
        self.deferred: list[Callable[[str | None], None]] = []

    def insert(self, job: Job) -> None:
        self.jobs[job.id] = job
        self.writes.append((job.id, job.status))

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def update(self, job: Job, done: Callable[[str | None], None] | None = None) -> None:
        """`ARC-005`'s asynchronous shape, completed synchronously **unless asked otherwise**.

        `defer_updates` is what makes the shape real. Completing every write inside the call makes
        a barrier untestable: an ordering rule that says "wait for these to settle" cannot fail
        when they have all settled before the next statement runs. A mutation removing `T115-R1`'s
        barrier survived the whole battery until this existed.
        """
        if job.id not in self.jobs:
            raise KeyError(job.id)
        self.jobs[job.id] = job
        self.writes.append((job.id, job.status))
        if done is None:
            return
        if self.defer_updates:
            self.deferred.append(done)
            return
        done(None)

    def release_updates(self) -> None:
        """Complete every held write, in the order it was asked for."""
        held, self.deferred = self.deferred, []
        self.defer_updates = False
        for done in held:
            done(None)

    def statuses(self, job_id: str) -> list[JobStatus]:
        return [status for stored_id, status in self.writes if stored_id == job_id]

    def requeue_at_end(self, job: Any, done: Any) -> None:
        """Part of `JobStore` since `T-080`. Unused here; present so the fake satisfies it."""
        raise NotImplementedError

    def remove(self, job_id: str, done: Callable[[str | None], None]) -> None:
        """Delete a row (`T-080`). **Exercised since `T-118`**, which withdraws by removing.

        `ARC-005`'s asynchronous shape, completed synchronously. The removed ids are recorded so a
        test can assert *which* row left rather than only that something did.
        """
        self.jobs.pop(job_id, None)
        self.removals.append(job_id)
        done(None)

    def reorder(self, job_ids: Any, done: Any) -> None:
        """Part of `JobStore` since `T-081`. Unused here; present so the fake satisfies it."""
        raise NotImplementedError

    def clear_completed(self, done: Any) -> None:
        """Part of `JobStore` since `T-081`. Unused here; present so the fake satisfies it."""
        raise NotImplementedError


class FakeSink:
    """A `JobSink` whose completion the test controls.

    Zero-latency by default, because most tests are about the dialog's logic rather than about
    storage. `defer=True` holds every submission until `release()`, which is how the ordering
    claims — persist *before* close, probe only after the write lands — are asserted without a
    sleep.
    """

    def __init__(self, store: FakeStore) -> None:
        self._store = store
        self.defer = False
        self.error: str | None = None
        self.pending: list[tuple[list[Job], Callable[[str | None], None]]] = []
        self.submissions: list[list[Job]] = []

    def submit(self, jobs: Sequence[Job], done: Callable[[str | None], None]) -> None:
        batch = list(jobs)
        self.submissions.append(batch)
        if self.defer:
            self.pending.append((batch, done))
            return
        self._apply(batch, done)

    def release(self) -> None:
        pending, self.pending = self.pending, []
        for batch, done in pending:
            self._apply(batch, done)

    def _apply(self, jobs: list[Job], done: Callable[[str | None], None]) -> None:
        if self.error is not None:
            done(self.error)
            return
        start = len(self._store.jobs)
        for offset, job in enumerate(jobs):
            self._store.insert(replace(job, queue_position=start + offset))
        done(None)


class RecordingThumbnailLoader:
    """Hands over real image bytes without a network, and records what it was asked for."""

    def __init__(self, data: bytes | None) -> None:
        self._data = data
        self.requested: list[str] = []
        self.cancels = 0

    def load(self, url: str, done: Callable[[bytes | None], None]) -> None:
        self.requested.append(url)
        done(self._data)

    def cancel(self) -> None:
        self.cancels += 1


# --- fixtures ---------------------------------------------------------------------------------


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def sink(store: FakeStore) -> FakeSink:
    return FakeSink(store)


@pytest.fixture
def managers(store: FakeStore, qapp: QApplication) -> Iterator[Callable[..., DownloadManager]]:
    """Builds managers and guarantees they are shut down, whatever the test did.

    Teardown is not tidiness: a leaked worker would outlive the test and be attributed to
    whichever one ran next.
    """
    built: list[DownloadManager] = []

    def build(**overrides: Any) -> DownloadManager:
        manager = DownloadManager(store, **overrides)
        manager.start_queue()
        built.append(manager)
        return manager

    yield build

    for manager in built:
        manager.shutdown()
    # Waits for the poll timer as well as the work — see `tests/qt_lifecycle.py` and `T-128`.
    drain(qapp, built)


@pytest.fixture
def thumbnails() -> RecordingThumbnailLoader:
    return RecordingThumbnailLoader(THUMBNAIL_SOURCE.read_bytes())


@pytest.fixture
def dialogs(
    sink: FakeSink,
    thumbnails: RecordingThumbnailLoader,
    tmp_path: Path,
    qapp: QApplication,
) -> Iterator[Callable[..., AddUrlDialog]]:
    """Builds dialogs and destroys them, so no widget outlives the test that made it."""
    built: list[AddUrlDialog] = []

    def build(manager: DownloadManager, **overrides: Any) -> AddUrlDialog:
        overrides.setdefault("jobs", sink)
        overrides.setdefault("thumbnail_loader", thumbnails)
        # **Never the real cache directory.** The store writes fetched thumbnails under
        # `NFR-004`'s cache root, and a test left on the default would write into the developer's
        # own — and then read them back on the next run, which is a test that passes because of
        # what a previous run left behind.
        overrides.setdefault("cache_root", tmp_path / "cache")
        dialog = AddUrlDialog(manager=manager, output_directory=tmp_path / "downloads", **overrides)
        built.append(dialog)
        return dialog

    yield build

    for dialog in built:
        dialog.close()
        dialog.deleteLater()
    qapp.processEvents()


# --- reading the dialog through its object names ----------------------------------------------


def label(dialog: AddUrlDialog, name: str) -> QLabel:
    found = dialog.findChild(QLabel, name)
    assert found is not None, f"no QLabel named {name!r}"
    return found


def button(dialog: AddUrlDialog, name: str) -> QPushButton:
    found = dialog.findChild(QPushButton, name)
    assert found is not None, f"no QPushButton named {name!r}"
    return found


def text_of(dialog: AddUrlDialog, name: str) -> str:
    return label(dialog, name).text()


def type_urls(dialog: AddUrlDialog, text: str) -> None:
    box = dialog.findChild(QPlainTextEdit, "urlInput")
    assert box is not None
    box.setPlainText(text)


def choose_preset(dialog: AddUrlDialog, name: str) -> None:
    box = dialog.findChild(QComboBox, "presetChoice")
    assert box is not None
    box.setCurrentText(name)


def choose_bitrate(dialog: AddUrlDialog, kbps: str) -> None:
    box = dialog.findChild(QComboBox, "audioBitrateChoice")
    assert box is not None
    index = box.findData(kbps)
    assert index >= 0, f"no {kbps} kbps entry; offered {preset_registry.MP3_BITRATES}"
    box.setCurrentIndex(index)


def focusable_widgets(dialog: AddUrlDialog) -> list[QWidget]:
    """Every keyboard-focusable widget belonging to this dialog's own window.

    The only exclusion is by **window**, not by name: `QComboBox` owns a popup `QListView` that is
    focusable but lives in its own top-level window and is never in the dialog's tab chain.
    Excluding by name is what `T016-R4` found — the observation filtered to the declared subset,
    so undeclared focusable controls could not fail it.
    """
    return [
        widget
        for widget in dialog.findChildren(QWidget)
        if widget.focusPolicy() & Qt.FocusPolicy.TabFocus and widget.window() is dialog
    ]


def states(dialog: AddUrlDialog) -> list[RowState]:
    """What each visible row has got to, in entry order."""
    return [row.state for row in dialog.rows]


def staging_list(dialog: AddUrlDialog) -> QListView:
    """The list widget, by the name it is declared under."""
    listing = dialog.findChild(QListView, "stagingList")
    assert listing is not None, "the staging list is not present under its declared name"
    return listing


def role_values(dialog: AddUrlDialog, role: int) -> list[Any]:
    """One role for every row, read **through the view's own model**.

    The distinction the widget-reading version protected still holds: this goes through
    `listing.model()`, so a dialog whose rows resolved and whose view was never given them fails
    here — the `test_composition.py` failure mode of waiting on the store and asserting the view.
    What changed is only that the row's fields are roles now rather than an item's text, which is
    what lets one delegate draw this list and the queue (`T-119`).
    """
    listing = staging_list(dialog)
    model = listing.model()
    return [model.data(model.index(index, 0), role) for index in range(model.rowCount())]


def item_texts(dialog: AddUrlDialog) -> list[str]:
    """What each row reads as, whole — headline, detail and state, and what it downloads as."""
    return [str(value) for value in role_values(dialog, Qt.ItemDataRole.DisplayRole)]


def open_row_editor(dialog: AddUrlDialog, index: int) -> QComboBox:
    """Open one row's format control the way the keyboard route does, and hand it back.

    Through `edit_row`, which is what `EDIT_KEY` and the context menu both reach (`T118-R9`). A
    test that reached into the delegate would prove the delegate builds a combo box; this proves
    the dialog offers one *on the row*, which is the finding.
    """
    assert dialog.edit_row(index), f"row {index} offered no format control"
    open_controls = staging_list(dialog).findChildren(QComboBox, ROW_PRESET_NAME)
    assert len(open_controls) == 1, (
        f"{len(open_controls)} row controls exist at once; the delegate opens exactly one "
        "(T118-R10), so this is either a leak or a previous editor that was never reaped"
    )
    return open_controls[0]


def choose_in_editor(dialog: AddUrlDialog, control: QComboBox, preset_name: str | None) -> None:
    """Pick an entry and close the editor, so the model takes the choice as Qt would deliver it.

    Draining the queue at the end is not decoration: `closeEditor` retires the widget with
    `deleteLater`, so without this the *next* `open_row_editor` finds two controls — the new one
    and a dead one — and `commitData` is then handed an editor the view has already let go of.
    `DeferredDelete` needs asking for **by name**: plain `processEvents` does not deliver it, which
    is why the first version of this helper left the editor standing.
    """
    listing = staging_list(dialog)
    # **`T-203` rerouted the verbs, twice.** The three per-row commands left the combo for the
    # verb bar, and `UX-011` then moved them into **the row's own menu** (option *E*). So a
    # sentinel here is driven the way a user now drives it: close the editor, open the current
    # row's menu, choose the entry. Every older test keeps describing the same gesture — "open
    # the formats for this row" — by its real route.
    verb_texts = {
        CHOOSE_FORMATS_DATA: CHOOSE_FORMATS_TEXT,
        OPTIONS_DATA: OPTIONS_TEXT,
        TEMPLATE_DATA: TEMPLATE_TEXT,
    }
    if preset_name in verb_texts:
        listing.closeEditor(control, QAbstractItemDelegate.EndEditHint.NoHint)
        QApplication.processEvents()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        current = listing.currentIndex()
        assert current.isValid(), "no row is current, so the menu has no row to be opened from"
        row = dialog._model.row_at(current.row())
        assert row is not None
        wanted = [
            action
            for action in dialog.row_menu(row).actions()
            if action.text() == verb_texts[preset_name]
        ]
        assert wanted, f"the row's menu does not offer {verb_texts[preset_name]!r}"
        wanted[0].trigger()
        QApplication.processEvents()
        return
    control.setCurrentIndex(control.findData(preset_name))
    listing.commitData(control)
    listing.closeEditor(control, QAbstractItemDelegate.EndEditHint.NoHint)
    QApplication.processEvents()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


#: The width a row is rendered at in these tests. Wide enough that nothing under test is elided.
RENDER_WIDTH: Final = 700


def render_rows(dialog: AddUrlDialog, *indices: int) -> QImage:
    """Paint the named rows through the real delegate, and answer what was drawn.

    **This is what "the view asked to paint a row" means**, and the tests about fetching depend on
    it being the only route: `RowDelegate.paint` is where `ThumbnailStore.pixmap` is called, so a
    row not named here has genuinely never been painted (`T-119`).

    Rows are drawn stacked, each `ROW_HEIGHT` tall, so one image can carry several.
    """
    listing = staging_list(dialog)
    delegate = listing.itemDelegate()
    model = listing.model()

    image = QImage(RENDER_WIDTH, ROW_HEIGHT * max(len(indices), 1), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        for slot, index in enumerate(indices):
            option = QStyleOptionViewItem()
            option.rect = QRect(0, slot * ROW_HEIGHT, RENDER_WIDTH, ROW_HEIGHT)
            option.font = listing.font()
            option.fontMetrics = QFontMetrics(option.font)
            option.palette = listing.palette()
            delegate.paint(painter, option, model.index(index, 0))
    finally:
        painter.end()
    return image


def tile_colour(image: QImage, slot: int = 0) -> QColor:
    """The colour of one drawn row's thumbnail box, sampled inside it."""
    return QColor(image.pixel(PADDING + 4, slot * ROW_HEIGHT + PADDING + 4))


def resolved(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    *names: str,
    entry_point: Any = child_replaying_a_fixture,
    **overrides: Any,
) -> tuple[AddUrlDialog, DownloadManager]:
    """Paste fixture-backed URLs and return once every row has settled.

    **Waits on the dialog's own rows**, not on the store: a test that waited on persistence and
    then asserted the view would pass while the list still showed the old state, which is the
    module docstring `test_composition.py` had to learn.
    """
    manager = managers(entry_point=entry_point)
    dialog = dialogs(manager, **overrides)
    type_urls(dialog, "\n".join(fixture_url(name) for name in names))
    dialog.resolve()
    assert spin(lambda: all(state in SETTLED for state in states(dialog)) and bool(dialog.rows)), (
        f"the rows never settled: {states(dialog)}"
    )
    assert spin(lambda: manager.is_idle), "a probe session was never released"
    return dialog, manager


def live_session_process(manager: DownloadManager, job_id: str) -> Any:
    """The worker process the manager is holding for `job_id`.

    Reads the manager's own record rather than searching the process table: the claim under test
    is that the manager left nothing behind, and its bookkeeping is what has to agree with the
    operating system.
    """
    return manager._sessions[job_id].process


def session_job_ids(manager: DownloadManager) -> tuple[str, ...]:
    """The jobs that actually have a worker — not the ones whose start is merely reserved.

    `active_job_ids()` reports both since `T016-R3`, because a reservation *is* work in flight
    and hiding it is what let shutdown announce `idle` and then spawn. A test about **worker
    construction** therefore has to ask about sessions specifically, or it would pass on a
    reservation and prove nothing about the process.
    """
    return tuple(manager._sessions)


# --- 1. UX-003: nothing enters the queue unprobed ----------------------------------------------


def test_pasting_resolves_every_line_without_a_second_control(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`UX-003`: the paste is the batch, and there is nothing else to press.

    The dialog this replaced had a `Probe first URL` button and probed exactly that. Everything
    else a user pasted went into the queue never having been looked at, which is where a
    title-less row came from — so the assertion is on **every** row, not on the first.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM, AUDIO_ONLY, PLAYLIST)

    assert states(dialog) == [RowState.READY, RowState.READY, RowState.READY]
    assert dialog.findChild(QPushButton, "probeButton") is None, (
        "the probe button survived the rewrite, so there is still a route to an unread URL"
    )


def test_every_row_shows_the_fields_req_002_names(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`REQ-002`, per row rather than for the one that happened to be probed.

    Read from the **list widget**, not from the rows: a dialog whose model resolved and whose list
    never repainted would pass an assertion on `dialog.rows` and show the user nothing.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM, PLAYLIST)
    info = load_info(SINGLE_ITEM)

    shown = item_texts(dialog)
    assert len(shown) == 2
    assert info["title"] in shown[0]
    assert "Playlist" in shown[1], f"a playlist did not say so: {shown[1]!r}"
    assert STATE_TEXT[RowState.READY] in shown[0]
    # Uploader and duration come from the same rendering, so one row proves the whole set.
    assert row_text(dialog.rows[0]).count(" · ") == 2, "a REQ-002 field is missing from the row"


def test_add_commits_what_resolved_and_leaves_what_did_not(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """`UX-003`'s first rule: a URL that will not read never becomes queued work.

    The unreadable line is not a fixture, so `child_replaying_a_fixture` never answers for it —
    which is the honest shape of a URL that hangs. It is removed rather than waited on, and the
    assertion is that the commit counted **one**, not two.
    """
    manager = managers(entry_point=child_failing_as_recorded)
    dialog = dialogs(manager)
    type_urls(dialog, f"{fixture_url(SINGLE_ITEM)}\nhttps://unreadable.invalid/x")
    dialog.resolve()
    assert spin(lambda: all(state in SETTLED for state in states(dialog)) and len(dialog.rows) == 2)

    assert states(dialog) == [RowState.FAILED, RowState.FAILED], (
        "this child fails everything; if one row resolved the test is not about what it says"
    )
    dialog.add_to_queue()

    assert dialog.queued_job_ids == (), "an unread URL was committed"
    assert all(job.status is not JobStatus.RUNNING for job in store.jobs.values())


def test_a_mixed_batch_commits_only_the_rows_that_were_read(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """`UX-003`, and **the filter itself** rather than something downstream of it.

    A mutation making Add commit every visible row survived a batch where everything failed:
    `retarget` refuses a `FAILED` job, the commit aborts, and `queued_job_ids` is empty either
    way. Relying on that refusal is `T081-R4` exactly — the filter is the guarantee, and a
    downstream guard is not a substitute for it.

    One readable URL and one that is not, so the correct answer (**one** committed) and the
    mutant's (none, because the batch aborts on the failed row) are different numbers.
    """
    manager = managers(entry_point=child_replaying_or_failing)
    dialog = dialogs(manager)
    type_urls(dialog, f"{fixture_url(SINGLE_ITEM)}\nhttps://no-fixture.invalid/x")
    dialog.resolve()
    assert spin(lambda: states(dialog) == [RowState.READY, RowState.FAILED]), states(dialog)

    dialog.add_to_queue()

    assert len(dialog.queued_job_ids) == 1, (
        f"the commit was {dialog.queued_job_ids}, not the one row that had been read"
    )
    committed = dialog.queued_job_ids[0]
    assert store.jobs[committed].url == fixture_url(SINGLE_ITEM), "the wrong row was committed"
    assert store.jobs[committed].status is JobStatus.RUNNING


def test_every_row_carries_its_own_format_control(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """`UX-004`, `T118-R4`: every row offers a control, and the request is built from it at Add.

    **One editor, opened on the row being edited** (`T118-R10`). The maintainer's choice was a real
    control on the row, and this is it — what changed is that the control is a delegate editor
    rather than a widget parked on every row, which is what removed the 0.722 s. *Offers* is
    therefore the claim: each row is editable, and opening one yields the declared control.

    Asserted end to end — open the control, choose, commit, read the stored request — because a
    per-row override that is not carried into the durable job is a control that does nothing.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM, AUDIO_ONLY)
    listing = staging_list(dialog)
    model = listing.model()

    assert model.rowCount() == 2
    for index in range(2):
        flags = model.flags(model.index(index, 0))
        assert flags & Qt.ItemFlag.ItemIsEditable, f"row {index} offers no format control"

    first = open_row_editor(dialog, 0)
    # The first entry means "the batch", spelled out rather than blank.
    assert first.itemData(0) is None
    assert first.itemText(0).strip(), "the inherited entry is blank, so it reads as no format"
    choose_in_editor(dialog, first, None)

    assert listing.findChildren(QComboBox, ROW_PRESET_NAME) == [], (
        "a row control outlived the row being edited, which is the cost T118-R10 was about"
    )

    second = open_row_editor(dialog, 1)
    choose_in_editor(dialog, second, "Audio only (MP3)")
    dialog.add_to_queue()

    committed = dialog.queued_job_ids
    assert len(committed) == 2
    assert store.jobs[committed[0]].request.media_kind is MediaKind.VIDEO, (
        "the untouched row did not follow the batch preset"
    )
    assert store.jobs[committed[1]].request.media_kind is MediaKind.AUDIO, (
        "the row's own preset was not what got queued"
    )


def test_an_overridden_row_downloads_at_the_bitrate_its_row_displays(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """`T118-R6` (Critical): the row's durable request must carry the *selected* MP3 quality.

    A row overridden to MP3 stored the registry preset verbatim, whose `audio_quality` is the
    192 kbps default — while the visible control said 320. `T-076` requires the displayed bitrate
    to be the one that runs and derives the preset precisely so the two cannot separate; the
    override reached for the raw preset and separated them again.

    **A non-default bitrate, deliberately.** The defect is invisible at 192: the wrong answer and
    the right one are the same number. The existing row test asserted only `media_kind`, which
    both bitrates satisfy, which is why a Critical survived it.

    Asserted on the durable `DownloadRequest` and on the row's own displayed text, because
    `T118-R8` is the same defect seen from the front: what the row says and what it does are one
    claim, not two.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM, AUDIO_ONLY)

    bitrate = dialog.findChild(QComboBox, "audioBitrateChoice")
    assert bitrate is not None
    wanted = "320"
    assert wanted != preset_registry.MP3_QUALITY, (
        "the registry default is now 320, so this test can no longer tell the two apart"
    )
    bitrate.setCurrentIndex(bitrate.findData(wanted))

    choose_in_editor(dialog, open_row_editor(dialog, 1), "Audio only (MP3)")

    # What the row promises, before anything is written.
    shown = item_texts(dialog)[1]
    assert f"{wanted} kbps" in shown, f"the row does not show the bitrate it will use: {shown!r}"

    dialog.add_to_queue()

    committed = dialog.queued_job_ids
    assert len(committed) == 2
    stored = store.jobs[committed[1]].request
    assert stored.audio_quality == wanted, (
        f"the row displayed {wanted} kbps and queued {stored.audio_quality} kbps"
    )


def test_an_overridden_row_shows_the_selector_that_will_run(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """`T118-R8`: the per-row *literal* selector, not just a preset name.

    `T-118` promises "the effective selector shown stays the one that will run". A row showed only
    a preset name, and the one literal selector on screen was the batch's — so choosing an audio
    override while the batch was video left the display describing the video download.

    A mixed batch is the case that separates them: each row's shown selector must equal its own
    durable request's `format_selector`, and the two rows must not agree.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM, AUDIO_ONLY)
    choose_in_editor(dialog, open_row_editor(dialog, 1), "Audio only (MP3)")

    shown = item_texts(dialog)
    dialog.add_to_queue()
    committed = dialog.queued_job_ids
    selectors = [store.jobs[job_id].request.format_selector for job_id in committed]

    assert selectors[0] != selectors[1], (
        "the batch and the overridden row resolved to the same selector, so this proves nothing"
    )
    for index, selector in enumerate(selectors):
        assert f"Format selector: {selector}" in shown[index], (
            f"row {index} shows {shown[index]!r} and will run {selector!r}"
        )


def test_a_failed_row_keeps_the_extractors_words_and_stays_on_screen(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`NFR-006`, `REQ-005`: character for character, and still visible so it can be retried.

    Refusing the whole paste was the alternative `UX-003` rejected: thirty URLs lost to eight
    timeouts. The row staying means a bad connection costs a button press.
    """
    dialog, _ = resolved(
        dialogs, managers, spin, SINGLE_ITEM, entry_point=child_failing_as_recorded
    )
    recorded = load_error("unsupported_url")["message"]

    assert states(dialog) == [RowState.FAILED]
    assert recorded in row_text(dialog.rows[0]), "the message was paraphrased"
    assert recorded in item_texts(dialog)[0], "the message never reached the list"
    assert button(dialog, "retryFailedButton").isEnabled()
    assert not button(dialog, "addButton").isEnabled(), "a failed batch offered to add itself"


def test_retrying_a_failed_row_reads_it_again_with_a_new_job(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """`UX-003`: a timeout costs a button press.

    A **new** job, not a restart in place: the old row is `FAILED` on disk and `ARC-004` has no
    edge from there back to `QUEUED` that does not go through the queue's own retry.
    """
    dialog, _ = resolved(
        dialogs, managers, spin, SINGLE_ITEM, entry_point=child_failing_as_recorded
    )
    first_job = dialog.rows[0].job_id
    assert first_job is not None

    dialog.retry_failed()
    assert spin(lambda: dialog.rows[0].job_id not in (None, first_job))

    assert dialog.rows[0].job_id != first_job, "the failed row was restarted in place"
    # **Removed, not cancelled.** `ARC-004` has `FAILED -> QUEUED` and nothing else, so cancelling
    # a failed row raises — and `REQ-018` would otherwise keep it in the queue offering a retry
    # for a URL the user never added.
    assert first_job not in store.jobs, (
        "the failed job was left in the database as work nobody is doing"
    )


def test_add_refuses_when_nothing_has_resolved(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
) -> None:
    """The button is disabled, and the method refuses anyway.

    Both, because a disabled button is a UI state and `add_to_queue` is reachable from a default
    button press and from a test. `UX-003` is a rule about the queue, not about a widget.
    """
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    type_urls(dialog, "https://nothing.invalid/x")

    assert not button(dialog, "addButton").isEnabled()
    dialog.add_to_queue()
    assert dialog.queued_job_ids == ()


# --- 2. resolution is debounced, and driven by the timer ---------------------------------------


def test_typing_does_not_start_a_probe_per_keystroke(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    sink: FakeSink,
) -> None:
    """A probe per character would spawn an interpreter per character (`ARC-002`).

    Asserted on **submissions**, not on sessions: a row is persisted before it can be probed, so
    a dialog that wrote a job per keystroke has already lost whatever it does next.
    """
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)

    for length in range(1, 12):
        type_urls(dialog, "https://a.invalid/x"[:length])

    assert sink.submissions == [], "typing wrote jobs before the input had settled"


def test_the_timer_resolves_what_typing_left_behind(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    sink: FakeSink,
    spin: Callable[..., bool],
) -> None:
    """The debounce is a delay, not a refusal — and the timer calls the same `resolve()`.

    Built with a zero delay so this waits on the event loop rather than on wall-clock time. What
    it proves is the wiring: `resolve()` is not a method only tests call.
    """
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager, resolve_delay_ms=0)
    assert dialog is not None

    type_urls(dialog, "https://a.invalid/x")

    # Observed on the *staging* probes, not on a write: `T118-R1` means resolving persists nothing.
    assert spin(lambda: bool(manager._staged)), "the timer never resolved the pasted URL"
    assert [job.url for job in manager._staged.values()] == ["https://a.invalid/x"]
    assert sink.submissions == [], "the debounce wrote a job, which UX-003 forbids before Add"


def test_resolving_does_not_persist_before_add(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
) -> None:
    """`UX-003`: resolving is transient; Add is the first durable queue operation.

    A database row is already queue intent in this application: composition admits durable
    `QUEUED` and `READY` rows on startup. Persisting one merely to obtain a probe id therefore
    turns a crash or an abandoned dialog into an unattended download.
    """
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    type_urls(dialog, "https://uncommitted.invalid/video")

    dialog.resolve()

    assert store.jobs == {}, "resolving persisted queue intent before Add was pressed"


def test_an_edit_during_pending_resolution_never_probes_the_old_url(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    sink: FakeSink,
) -> None:
    """A delayed callback must re-decide ownership against the current editor contents.

    This is the asynchronous form of `T016-R1`: the URL the user replaced must not become the
    request that runs merely because its earlier write happened to finish later.
    """
    sink.defer = True
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    old = "https://old.invalid/video"
    wanted = "https://wanted.invalid/video"
    type_urls(dialog, old)
    dialog.resolve()

    type_urls(dialog, wanted)
    dialog.resolve()
    sink.release()

    assert [row.url for row in dialog.rows] == [wanted]
    # **Restated for the corrected design, and strengthened.** The reviewer's original asserted the
    # replaced URL was absent from the last *submission*; under `T118-R1` resolving submits nothing
    # at all, so that assertion had no list to read. The claim is unchanged and now checked at the
    # two places it can fail: nothing was persisted, and no probe is still running for the URL the
    # user replaced.
    assert sink.submissions == [], "resolving persisted a job, which UX-003 forbids before Add"
    # A staged record outlives its own cancellation — the steps that stop a worker each read the
    # job on the way past — so the claim is that the replaced URL is *being stopped*, not that it
    # has already vanished. Asserting absence would be asserting a reap had finished, which is
    # timing rather than ownership.
    staged = manager._staged
    replaced = [job_id for job_id, job in staged.items() if job.url == old]
    assert replaced, "the old URL was never staged, so this proves nothing about replacing it"
    assert all(job_id in manager._unstaging for job_id in replaced), (
        "the replaced URL is still being read"
    )
    assert any(
        job.url == wanted and job_id not in manager._unstaging for job_id, job in staged.items()
    ), "the URL the user actually wants was never read"


def test_closing_during_pending_resolution_cannot_start_abandoned_work(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    sink: FakeSink,
    store: FakeStore,
    qapp: QApplication,
) -> None:
    """A close owns work whose asynchronous setup has not completed yet (`T016-R1`)."""
    sink.defer = True
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    type_urls(dialog, "https://abandoned.invalid/video")
    dialog.resolve()

    dialog.reject()
    sink.release()
    qapp.processEvents()

    assert store.jobs == {}, "a callback started work after its dialog had abandoned the paste"


# --- 3. T016-R1: a result belongs to a line, not to a job id -----------------------------------


def test_a_result_arriving_after_its_line_was_removed_is_refused(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """`T016-R1`, the Critical one, generalised from one probe to a batch.

    The row is superseded while its probe is still running, so the result lands for a line that is
    no longer entered. It must not become a committable row — and its job must be withdrawn rather
    than left durably `QUEUED`, where whatever runs the queue next would download it.
    """
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    type_urls(dialog, "https://gone.invalid/x")
    dialog.resolve()
    assert spin(lambda: bool(dialog.rows) and dialog.rows[0].in_flight)
    row = dialog.rows[0]
    job_id = row.job_id
    assert job_id is not None

    type_urls(dialog, "")
    dialog.resolve()

    assert dialog.rows == (), "the removed line is still on screen"
    assert row.state is RowState.SUPERSEDED
    # The late result, delivered by hand: the signal it would have ridden is already queued.
    dialog._on_media_probed(job_id, MediaInfo(url="https://gone.invalid/x", title="Too late"))
    assert row.state is RowState.SUPERSEDED, "a result was accepted for a line nobody is looking at"
    # Nothing to withdraw: the probe was never a queue row (`T118-R1`). What must be true is that
    # it left no durable trace and its worker was stopped.
    assert store.jobs == {}, "a staging probe wrote a row"


def test_editing_one_line_leaves_the_resolved_rows_alone(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """Appending to a paste must not re-read the lines above it.

    Asserted on the row's **identity and job id**: a row rebuilt from scratch carries the same URL
    while having lost its probe, which is the difference between editing a batch and re-entering
    one. Twenty rows re-read on every keystroke is the version of this that ships.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM)
    first = dialog.rows[0]
    original_job = first.job_id

    type_urls(dialog, f"{fixture_url(SINGLE_ITEM)}\nhttps://second.invalid/2")
    dialog.resolve()

    assert dialog.rows[0] is first, "an untouched line lost its row"
    assert dialog.rows[0].job_id == original_job
    assert dialog.rows[0].state is RowState.READY, "a resolved row was re-read"


def test_two_identical_lines_are_queued_twice(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`REQ-001`: the user asked for both.

    The quiet failure is one download for two lines, reported as a successful add.
    """
    url = fixture_url(SINGLE_ITEM)
    manager = managers(entry_point=child_replaying_a_fixture)
    dialog = dialogs(manager)
    type_urls(dialog, f"{url}\n{url}")
    dialog.resolve()
    assert spin(lambda: states(dialog) == [RowState.READY, RowState.READY])

    dialog.add_to_queue()

    assert len(dialog.queued_job_ids) == 2
    assert len(set(dialog.queued_job_ids)) == 2, "both lines were committed as one job"


# --- 4. T-075 and T115-R1: what runs, and in what order ----------------------------------------


def test_the_preset_selected_at_add_is_the_one_that_runs(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """`T-075`: the request that runs is the one selected **now**.

    A row is saved when it is pasted, from whichever preset was current then. Choosing a different
    one afterwards is the ordinary order — you read what something is before deciding how to take
    it — and the defect was that it changed the displayed selector and nothing else.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM)
    choose_preset(dialog, "Audio only (MP3)")

    dialog.add_to_queue()

    assert dialog.queued_job_ids, "nothing was committed"
    stored = store.jobs[dialog.queued_job_ids[0]].request
    assert stored.media_kind is MediaKind.AUDIO, (
        f"queued {stored.format_selector!r}, which is not what the dialog was showing"
    )


def test_the_batch_is_admitted_once_in_entry_order(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """`T115-R1`: one admission decision, in the order the rows were written.

    With a pool of one, admitting out of order starts the second URL while the row the user sees
    at the head of the list waits. `T-081` establishes that the table and the scheduler agree, and
    an asynchronous prerequisite does not get to suspend that.
    """
    dialog, manager = resolved(dialogs, managers, spin, SINGLE_ITEM, AUDIO_ONLY)
    wanted = [row.url for row in dialog.rows]

    dialog.add_to_queue()

    committed = dialog.queued_job_ids
    assert [store.jobs[job_id].url for job_id in committed] == wanted, (
        "the batch was committed out of entry order"
    )
    first, second = committed
    assert store.jobs[first].status is JobStatus.RUNNING, (
        "a later row took the only slot before the head of the queue"
    )
    assert store.jobs[second].status is JobStatus.READY
    assert set(manager.active_job_ids()) == {first, second}


# --- 5. T016-R2: closing abandons, and owns the outcome ----------------------------------------


def test_the_batch_is_admitted_only_after_its_rows_are_durable(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    sink: FakeSink,
    spin: Callable[..., bool],
) -> None:
    """`REQ-012`, and what replaced `T115-R1`'s retarget barrier.

    The batch used to be written first and *retargeted* to the chosen preset, so admission had to
    wait for every retarget to settle — `T118-R3` is the race that left behind. Each row is now
    written once, already carrying its final request, so the only thing to wait for is the write.

    **The write is deferred**, because with a synchronous sink this cannot fail: everything settles
    before the next statement runs and a barrier behaves identically to none.
    """
    dialog, manager = resolved(dialogs, managers, spin, SINGLE_ITEM, AUDIO_ONLY)
    admitted: list[str] = []
    original = manager.admit

    def recording(job_id: str, kind: SessionKind = SessionKind.DOWNLOAD) -> None:
        admitted.append(job_id)
        original(job_id, kind)

    manager.admit = recording  # type: ignore[method-assign]
    sink.defer = True

    try:
        dialog.add_to_queue()
        assert admitted == [], "the batch was admitted before its rows were durable"
        assert store.jobs == {}, "rows were in the store before the write completed"
    finally:
        # In a `finally` so a failure above does not leave the sink holding callbacks the
        # manager's shutdown is waiting on.
        sink.release()

    assert admitted == list(dialog.queued_job_ids), (
        f"admitted {admitted}, expected each committed row exactly once in entry order"
    )


def test_the_dialog_stays_open_until_its_commit_settles(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    sink: FakeSink,
    spin: Callable[..., bool],
) -> None:
    """`T118-R3`: the dialog owns the outcome of the Add the user pressed.

    It used to disappear while its rows were still being made durable, leaving nobody watching
    whether the commit worked — and, when a retarget then failed, a `READY` row in the queue
    carrying the *old* request for startup to download in the wrong format.

    Add is disabled for the whole commit as well, so a second click cannot schedule a duplicate.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM)
    # **Asserted on `finished`, which fires exactly once when a dialog actually closes.**
    # This read `dialog.isVisible() or not dialog.result()`. `reject()` sets the result to
    # `Rejected` — falsy — so the second half was true whether the dialog had closed or not, and a
    # mutation letting close abandon an unsettled commit survived the whole battery on that one
    # word. `isVisible()` alone is no better here: the dialog is never shown, so it is false either
    # way. The signal is the only thing that distinguishes the two outcomes.
    closed: list[int] = []
    dialog.finished.connect(closed.append)
    sink.defer = True

    try:
        dialog.add_to_queue()

        assert dialog.is_saving, "the commit is not owned"
        assert not button(dialog, "addButton").isEnabled(), "a second click would commit twice"
        dialog.reject()
        assert closed == [], "the dialog closed on an unsettled commit"
    finally:
        sink.release()

    assert dialog.queued_job_ids, "the commit never completed"


def test_closing_withdraws_every_row_it_did_not_commit(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """`T016-R2`, `UX-003`: a row that was never committed never becomes queued work.

    A row has to be persisted before it can be probed (`REQ-012`), so closing on it silently would
    leave live work a restart picks up — which is exactly `T016-R1`'s Critical consequence.
    """
    dialog, manager = resolved(dialogs, managers, spin, SINGLE_ITEM, AUDIO_ONLY)
    job_ids = [row.job_id for row in dialog.rows]
    assert all(job_id is not None for job_id in job_ids)

    dialog.reject()

    # **Nothing to withdraw, because nothing was ever written** (`T118-R1`). The earlier version
    # asserted the rows had been *removed* from the store; the ruling is stronger — they were
    # never in it, so there is no `CANCELLED` row and no delete.
    assert store.jobs == {}, f"resolving persisted rows: {sorted(store.jobs)}"
    assert store.removals == [], "a row was deleted, so one had been written"
    assert all(not manager.is_staged(str(job_id)) for job_id in job_ids), (
        "a staging probe outlived the dialog that started it"
    )


def test_a_committed_row_is_not_withdrawn_when_the_dialog_closes(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """The mirror image, and the one that would cancel the user's download.

    `add_to_queue` accepts, which reaches `done()` — so a `done()` that withdrew everything
    unresolved would cancel the job it had just started.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM)

    dialog.add_to_queue()
    assert spin(lambda: not dialog.isVisible())

    # The committed job is a **new, durable** id — the staging probe's id was never a queue row.
    committed = dialog.queued_job_ids
    assert len(committed) == 1
    assert committed[0] in store.jobs, "the committed row is not in the queue"
    assert store.jobs[committed[0]].status is not JobStatus.CANCELLED, (
        "closing cancelled the download the user had just added"
    )


def test_closing_mid_read_stops_the_probes_without_writing_anything(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """`T016-R2` and `T118-R1`: closing abandons the batch, and closing is immediate.

    The earlier version held the window open until a durable `CANCELLED` had been written for
    every row. There is nothing to write: a staging probe was never a queue row, so the dialog
    stops its workers and goes. What the queue never held, it never has to be told about.
    """
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    type_urls(dialog, "https://never.invalid/x\nhttps://never.invalid/y")
    dialog.resolve()
    assert spin(lambda: len(dialog.rows) == 2 and all(row.in_flight for row in dialog.rows))

    dialog.reject()

    assert store.jobs == {}, "closing left rows in the queue that were never committed"
    assert spin(lambda: manager.is_idle, timeout=60), "a probe outlived the dialog"


# --- 6. NFR-005 and T016-R6: reachable, named, and never interpreted ---------------------------


def test_the_keyboard_order_is_the_declared_one(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
) -> None:
    """`NFR-005`, `T016-R4`: transcribed by hand, and compared against **every** focusable widget.

    Deriving the expectation from `focus_chain()` proves only that the list equals itself, and
    filtering the observation to the declared names is how six focusable labels landed after Close
    and gated nothing.
    """
    dialog = dialogs(managers(entry_point=child_never_returning))

    reachable = [widget.objectName() for widget in focusable_widgets(dialog)]

    # **The row controls are counted, not named** (`UX-004`). Each row carries its own format
    # combo, so the focusable set grows with the paste — naming twenty of them would be naming the
    # paste rather than the dialog. They all share one object name and are asserted per row by
    # `test_every_row_carries_its_own_format_control`; what this owns is the fixed surface.
    fixed = [name for name in reachable if name != ROW_PRESET_NAME]
    assert sorted(fixed) == sorted(EXPECTED_TAB_ORDER), (
        f"the fixed focusable set is not the declared one: {sorted(fixed)}"
    )
    assert [widget.objectName() for widget in dialog.focus_chain()] == list(EXPECTED_TAB_ORDER)


def test_no_widget_in_the_chain_is_hidden(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
) -> None:
    """`T-060`: a hidden widget in the chain is a Tab stop that goes nowhere.

    The retry control is **disabled** when nothing has failed rather than removed, so the chain is
    the same in every state and the layout does not move under the user.
    """
    dialog = dialogs(managers(entry_point=child_never_returning))
    dialog.show()
    try:
        assert not button(dialog, "retryFailedButton").isEnabled(), "nothing has failed yet"
        assert all(not widget.isHidden() for widget in dialog.focus_chain())
    finally:
        dialog.hide()


def test_a_markup_title_is_shown_rather_than_interpreted(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`T016-R6`: a title of `<b>VISIBLE</b>` is a title, not markup.

    Not hypothetical — a title is arbitrary text chosen by whoever uploaded the item, and `<b>` is
    two keystrokes. A `QListWidgetItem` renders plain text by construction, which is *why* the
    list is items rather than rich-text widgets; this pins that it stays that way.
    """
    manager = managers(entry_point=child_probing_a_markup_title)
    dialog = dialogs(manager)
    type_urls(dialog, "https://markup.invalid/x")
    dialog.resolve()
    assert spin(lambda: states(dialog) == [RowState.READY])

    assert "<b>VISIBLE</b>" in item_texts(dialog)[0], "the tags were consumed as markup"


def test_every_state_is_named_in_words(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`NFR-005`: never a colour alone, and asserted over **every** state the enum has.

    A state added without a sentence fails here rather than shipping as a tile whose meaning is
    only its hue.
    """
    assert set(STATE_TEXT) == set(RowState), "a row state has no words to describe it"

    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM)
    assert STATE_TEXT[RowState.READY] in item_texts(dialog)[0]


def test_a_row_carries_its_accessible_text(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`NFR-005`: everything a sighted user reads from the row is available to a screen reader."""
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM)

    spoken = role_values(dialog, Qt.ItemDataRole.AccessibleTextRole)[0]

    assert isinstance(spoken, str) and spoken
    assert load_info(SINGLE_ITEM)["title"] in spoken
    assert "\n" not in spoken, "a newline reads as nothing; the lines must be one sentence"
    # **The control a sighted user can see, announced to someone who cannot** (`T118-R9`,
    # `NFR-005`). The editor is not a tab stop, so without this sentence the only route to it is
    # one a screen-reader user has no way of discovering.
    assert EDIT_HINT in spoken, "the keyboard route to the row's control is never announced"


# --- 7. every row is filled, from the moment it appears ----------------------------------------


def test_a_row_has_a_tile_before_it_has_a_thumbnail(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`UX-003`: never an empty well.

    A column of empty boxes reads as a broken application, and reads worse the more URLs are
    pasted — which is the case this design is for. The tile is derived from the URL, so it is
    there from the first frame.
    """
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    type_urls(dialog, "https://a.invalid/1\nhttps://b.invalid/2")
    dialog.resolve()
    assert spin(lambda: len(dialog.rows) == 2)

    drawn = render_rows(dialog, 0, 1)
    background = QColor(drawn.pixel(RENDER_WIDTH - 1, ROW_HEIGHT - 1))
    for slot in range(2):
        assert tile_colour(drawn, slot) != background, f"row {slot} was drawn as an empty well"

    # **And the two tiles are not the same tile** (`NFR-005`): the placeholder is decoration, so
    # two rows that differ only by it would be two rows a user cannot tell apart.
    assert tile_colour(drawn, 0) != tile_colour(drawn, 1), (
        "both rows drew the same derived tile, so it distinguishes nothing"
    )


def test_a_probed_thumbnail_replaces_the_derived_tile(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    thumbnails: RecordingThumbnailLoader,
    spin: Callable[..., bool],
) -> None:
    """The tile is a placeholder, not the answer. Qt decodes the bytes for real.

    **The paint is what starts it** (`T-119`). Resolving alone fetches nothing now, which is the
    whole of "no fetch for a row the view never asked to paint" — so this renders the row first,
    then waits for the decode, which happens off the GUI thread (`ARC-005`).
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM)

    assert not thumbnails.requested, "a thumbnail was fetched before any row was painted"
    # **Asking must not fetch either.** `thumbnail_for` goes through `peek`, and if it went
    # through `pixmap` instead then anything that merely wondered whether a row had a picture
    # would become a second fetch path — and "no fetch for a row the view never painted" would be
    # false whenever a test, or the dialog itself, asked the question.
    assert dialog.thumbnail_for(dialog.rows[0]) is None
    assert dialog.thumbnails.pending_urls == frozenset(), (
        "asking whether a row has a picture started fetching one"
    )

    render_rows(dialog, 0)
    assert spin(lambda: dialog.thumbnail_for(dialog.rows[0]) is not None), (
        "the fetched bytes never became a pixmap"
    )
    assert thumbnails.requested, "no thumbnail was ever fetched for a painted row"


def test_a_thumbnail_that_will_not_decode_leaves_the_tile_alone(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    sink: FakeSink,
    tmp_path: Path,
    qapp: QApplication,
    spin: Callable[..., bool],
) -> None:
    """`T016-R5`, and `T-119`'s rule early: a missing picture is not a failed download.

    Undecodable bytes and a failed fetch are the same thing to a user — no picture — and neither
    is worth reporting as an error beside a row that resolved perfectly well.
    """
    manager = managers(entry_point=child_replaying_a_fixture)
    loader = RecordingThumbnailLoader(b"not an image")
    dialog = dialogs(manager, thumbnail_loader=loader)
    type_urls(dialog, fixture_url(SINGLE_ITEM))
    dialog.resolve()
    assert spin(lambda: states(dialog) == [RowState.READY])

    drawn = render_rows(dialog, 0)
    assert spin(lambda: bool(loader.requested)), "the painted row never asked for its picture"
    qapp.processEvents()

    assert dialog.thumbnail_for(dialog.rows[0]) is None
    assert states(dialog) == [RowState.READY], "an undecodable picture failed the row"
    background = QColor(drawn.pixel(RENDER_WIDTH - 1, ROW_HEIGHT - 1))
    assert tile_colour(drawn) != background, "the derived tile went with the failed decode"

    # **And it is not asked for again** (`T-119`): a row repaints constantly, and retrying a URL
    # that will not decode on every paint is a request loop nobody asked for.
    before = len(loader.requested)
    for _ in range(5):
        render_rows(dialog, 0)
        qapp.processEvents()
    assert len(loader.requested) == before, (
        f"a failed thumbnail was re-fetched on repaint: {before} then {len(loader.requested)}"
    )


# --- 8. scale: a public application cannot assume twenty ---------------------------------------


def test_a_paste_the_design_supports_stays_inside_the_interaction_budget(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    sink: FakeSink,
) -> None:
    """`NFR-001`: pasting five hundred URLs must not be five hundred of anything on the GUI thread.

    Asserted on the **submission count**, which is the thing that would multiply: one batch write,
    one reconcile, one model reset. The probe lane bounds the sessions (`T-116`); the delegate is
    what bounds the widgets, at one — see `INTERACTION_BUDGET_SECONDS`.
    """
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    urls = "\n".join(f"https://many.invalid/{n}" for n in range(SUPPORTED_PASTE))

    started = time.monotonic()
    type_urls(dialog, urls)
    dialog.resolve()
    elapsed = time.monotonic() - started

    assert sink.submissions == [], "resolving wrote jobs, which UX-003 forbids before Add"
    assert len(dialog.rows) == SUPPORTED_PASTE
    assert elapsed < INTERACTION_BUDGET_SECONDS, (
        f"resolving {SUPPORTED_PASTE} URLs blocked the GUI thread for {elapsed:.3f}s"
    )
    # **The surplus queues; it is not refused** (`T-116`). The probe lane holds
    # `DEFAULT_PROBE_CONCURRENCY` at a time, and `start()` raises once it is full — which is why
    # the dialog admits instead. A mutation swapping `admit` for `start` here leaves every row
    # past the fourth `FAILED` with "the probe lane is full", and nothing else noticed.
    refused = [row for row in dialog.rows if row.state is RowState.FAILED]
    assert not refused, (
        f"{len(refused)} rows were refused rather than queued behind the probe lane; "
        f"the first says: {refused[0].message!r}"
    )
    assert sum(1 for row in dialog.rows if row.state is RowState.PROBING) <= (
        DEFAULT_PROBE_CONCURRENCY
    ), "more probes ran at once than the lane allows"


def test_a_large_paste_builds_no_control_at_all_until_one_is_asked_for(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
) -> None:
    """`T118-R10`, **structurally** — the claim the two timing tests cannot make.

    Both of those measure a dialog that is never shown, and a hidden view lays nothing out: a
    mutation reintroducing a persistent editor per row passed both, because five hundred unshown
    combo boxes are cheap on this platform and ruinous on the one that measured 0.722 s. Counting
    the live widgets says the thing directly and says it the same on every machine.

    **At most one, not zero** (`T118-R12`). The first version of this test demanded zero live
    controls at all times, which the review correctly read as *encoding* the missing affordance
    rather than catching it: a row with no visible control passed it, and `UX-004` requires one on
    every row. What scales is the number of live `QComboBox` widgets; what `UX-004` requires is
    that every row *shows* a control. The two are only compatible because the delegate paints the
    control and instantiates one — which is `UX-004`'s own "C" — so this asserts the widget count
    and `test_every_row_shows_its_download_as_control` asserts the visible half.
    """
    dialog = dialogs(managers(entry_point=child_never_returning))
    type_urls(dialog, "\n".join(f"https://many.invalid/{n}" for n in range(SUPPORTED_PASTE)))
    dialog.resolve()

    assert len(dialog.rows) == SUPPORTED_PASTE
    controls = staging_list(dialog).findChildren(QComboBox, ROW_PRESET_NAME)
    assert len(controls) <= 1, (
        f"{len(controls)} live per-row controls exist for {SUPPORTED_PASTE} rows; the delegate "
        "paints the control and instantiates at most one, for the row being edited"
    )


def test_every_resolved_row_offers_its_download_as_control(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`UX-004` §1, `T118-R12`: every row that can be retargeted says so.

    The dialog's half of the claim — that each resolved row offers the control and carries its
    current value. That the control is actually *drawn* is
    `test_row_delegate.test_a_row_with_choices_draws_a_control_and_one_without_does_not`, which
    can hold the two rows identical apart from the choices and so isolates the drawing.

    An earlier version of this test rendered the slot and asserted it was "not blank". It passed
    with the control's painting disabled, because the item background fills that rectangle either
    way — the same class of vacuous assertion the review was about, produced while fixing it.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM, AUDIO_ONLY)
    model = staging_list(dialog).model()

    for index in range(model.rowCount()):
        cell = model.index(index, 0)
        assert model.data(cell, PRESET_CHOICES_ROLE), f"row {index} offers no format choices"
        assert cell.flags() & Qt.ItemFlag.ItemIsEditable, f"row {index} is not editable"

    # Spelled out rather than blank (`T118-R4`): a row following the batch reads as the inherited
    # entry, which is what the control draws when the row has no preset of its own.
    assert role_values(dialog, PRESET_ROLE) == [None, None]
    assert INHERITED_TEXT.strip(), "the inherited entry has no words for the control to draw"


def test_clicking_a_rows_control_opens_it_without_selecting_first(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    qapp: QApplication,
    spin: Callable[..., bool],
) -> None:
    """`T118-R12`: the drawn control is a control, not a picture of one.

    `SelectedClicked` alone made the first click select the row and do nothing visible, so the user
    had to click the same place twice with no way to know that. A click inside the control's own
    rectangle opens the editor on the row it belongs to, whether or not that row was selected.

    Driven through the delegate's `editorEvent` with a real mouse event at real coordinates —
    a test that called `edit_row()` would prove the programmatic route the review already had.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM, AUDIO_ONLY)
    listing = staging_list(dialog)
    dialog.show()
    try:
        qapp.processEvents()
        listing.clearSelection()
        listing.setCurrentIndex(QModelIndex())

        target = listing.model().index(1, 0)
        rect = listing.visualRect(target)
        # **Aimed from the delegate's own rectangle, not from the row's centre** (`T-136`). This
        # used `rect.center().y()`, which was inside the control only while it was centred in the
        # whole row — and `T-136` moved it up beside the first two lines, because centred meant
        # "across the selector line". A test that aims at a coordinate the delegate does not
        # publish is a test that pins the layout it happened to be written against.
        delegate = listing.itemDelegate()
        assert isinstance(delegate, RowDelegate)
        body = rect.adjusted(PADDING, PADDING, -PADDING, -PADDING)
        control = delegate._control_rect(body, QFontMetrics(listing.font()).height()).center()
        QTest.mouseClick(listing.viewport(), Qt.MouseButton.LeftButton, pos=control)
        qapp.processEvents()

        opened = listing.findChildren(QComboBox, ROW_PRESET_NAME)
        assert len(opened) == 1, (
            f"one click on row 1's control opened {len(opened)} editors; it must open exactly one"
        )
        assert listing.currentIndex().row() == 1, "the editor opened on the wrong row"
    finally:
        dialog.hide()


def test_a_rows_open_editor_survives_another_row_settling(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    qapp: QApplication,
    spin: Callable[..., bool],
) -> None:
    """`T118-R14`: choosing a format must survive a *sibling* row finishing its probe.

    `StagingModel.refresh()` reset the model for every value change, and a reset invalidates the
    live editor's model index. Qt then disowns the widget: committing it reports *"called with an
    editor that does not belong to this view"*, `setData` is never reached, and the chosen format
    is discarded while the orphaned control stays on screen. The trigger is ordinary — another row
    resolving while the user is mid-choice — not teardown.

    Driven on a **shown** dialog and asserted all the way to the durable request, because the
    finding is that the visible choice silently fails to become the queued one.
    """
    manager = managers(entry_point=child_replaying_a_fixture)
    dialog = dialogs(manager)
    dialog.show()
    try:
        type_urls(dialog, f"{fixture_url(AUDIO_ONLY)}\n{fixture_url(SINGLE_ITEM)}")
        dialog.resolve()
        assert spin(lambda: states(dialog) == [RowState.READY, RowState.READY])

        control = open_row_editor(dialog, 0)
        control.setCurrentIndex(control.findData("Audio only (MP3)"))

        # Row 1 settles again while row 0's editor is open — the value-only refresh that used to
        # reset the model out from under it.
        dialog._refresh()
        qapp.processEvents()

        still_open = staging_list(dialog).findChildren(QComboBox, ROW_PRESET_NAME)
        assert still_open == [control], "the open editor was orphaned by a refresh of another row"

        choose_in_editor(dialog, control, "Audio only (MP3)")
    finally:
        dialog.hide()

    assert isinstance(dialog.rows[0].preset, Preset), "the chosen format never reached the row"
    assert dialog.preset_for(dialog.rows[0]).media_kind is MediaKind.AUDIO

    dialog.add_to_queue()
    committed = dialog.queued_job_ids
    assert len(committed) == 2
    assert store.jobs[committed[0]].request.media_kind is MediaKind.AUDIO, (
        "the row's visible choice was not what got queued"
    )


def test_the_literal_selector_survives_at_a_realistic_width(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`T118-R8`, `REQ-009`: the **rendered** selector, not the model's copy of it.

    The previous correction put the right string in `SELECTOR_ROLE` and then right-elided it at the
    width left over beside the control — 382 px against a built-in that measures up to 962 px — so
    the literal selector was cut off entirely and the tests, which read `DisplayRole`, never saw
    it. This asserts what a sighted user can actually read.

    The measurement is the delegate's own wrapped layout, so it fails if the line goes back to one
    line, gets narrowed by the control's slot again, or is elided.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM)
    row = dialog.rows[0]
    selector = preset_registry.effective_selector(dialog.preset_for(row))

    listing = staging_list(dialog)
    metrics = QFontMetrics(listing.font())
    available = QRect(0, 0, RENDER_WIDTH - 2 * PADDING - THUMBNAIL_SIZE[0] - GAP, ROW_HEIGHT)
    drawn = metrics.boundingRect(
        available,
        int(Qt.TextFlag.TextWordWrap),
        role_values(dialog, SELECTOR_ROLE)[0],
    )

    assert selector in role_values(dialog, SELECTOR_ROLE)[0], "the row does not carry its selector"
    assert drawn.height() <= SELECTOR_LINES * metrics.height(), (
        f"the selector needs {drawn.height()}px and the row draws {SELECTOR_LINES} lines "
        f"({SELECTOR_LINES * metrics.height()}px), so it would be cut off"
    )
    assert drawn.width() <= available.width(), "the selector was measured wider than it is drawn"


def test_a_choice_made_during_the_debounce_lands_on_the_row_it_was_made_for(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    qapp: QApplication,
    spin: Callable[..., bool],
) -> None:
    """`T118-R14` as **Critical**: a per-row format assigned to the wrong URL.

    The user route, exactly as the review traced it. Start with A, B, C. Edit the box to B, C —
    which opens the debounce window and reconciles staging *before* the model is told. Open the
    editor on what is still row 1 — B — and choose MP3. Let `resolve()` run.

    The old model index 1 named B; the new visible tuple is (B, C), where index 1 is **C**. The
    index stayed numerically valid and stopped naming the same row, so committing it wrote MP3
    into C and left B inherited. Add would then durably queue the wrong request for both — the
    silent wrong-format consequence that made `T118-R6` Critical, reached from a new direction.

    The previous regression called `_refresh()` with an unchanged row tuple, so it exercised only
    the value-only branch and could never reach this shift. Asserted on **both** surviving rows and
    on both durable requests, so applying the choice to the following URL cannot pass.
    """
    manager = managers(entry_point=child_replaying_a_fixture)
    dialog = dialogs(manager)
    dialog.show()
    try:
        first, second, third = (
            fixture_url(SINGLE_ITEM),
            fixture_url(AUDIO_ONLY),
            fixture_url(PLAYLIST),
        )
        type_urls(dialog, f"{first}\n{second}\n{third}")
        dialog.resolve()
        assert spin(lambda: states(dialog) == [RowState.READY] * 3)
        kept_b, kept_c = dialog.rows[1], dialog.rows[2]

        # The user drops the first line. `type_urls` starts the debounce; nothing has reconciled.
        type_urls(dialog, f"{second}\n{third}")
        control = open_row_editor(dialog, 1)
        assert dialog.model.row_at(1) is kept_b, "row 1 is not B, so this is not the reported case"
        control.setCurrentIndex(control.findData("Audio only (MP3)"))

        # **The model must still answer for what the view believes** right up to the reset, or the
        # commit above resolves against a tuple the user never saw. Checked from
        # `modelAboutToBeReset`, which is the last moment the old indices are still in force —
        # otherwise this invariant is internal to one call and nothing outside can see it.
        seen: list[tuple[Row | None, Any, int]] = []

        def sample() -> None:
            """Both halves of the invariant: which row index 1 names, and what the model *says*
            about it. `data()` matters as much as `row_at` — a model whose text comes from live
            staging while its writes go to the snapshot is two different models."""
            cell = dialog.model.index(1, 0)
            seen.append(
                (
                    dialog.model.row_at(1),
                    dialog.model.data(cell, HEADLINE_ROLE),
                    dialog.model.rowCount(),
                )
            )

        dialog.model.modelAboutToBeReset.connect(sample)

        # The debounce fires: staging reconciles to (B, C) and the model resets under the editor.
        dialog.resolve()
        # **One structural change is one reset** — `setData` calls back into `refresh()`, so
        # without the re-entrancy guard the reset happens inside itself. Counted here rather than
        # after the spin, because the debounce timer legitimately produces later ones.
        assert len(seen) == 1, f"one reconcile produced {len(seen)} resets: {seen!r}"
        qapp.processEvents()
        assert spin(lambda: states(dialog) == [RowState.READY, RowState.READY])

        # **The first reset** — the one that swaps A out, which is the one the finding is about.
        # Later resets legitimately resolve index 1 to C, because by then that is what it means.
        assert seen and seen[0] == (kept_b, load_info(AUDIO_ONLY)["title"], 3), (
            "at the reset that removed A, the model resolved row 1 to something other than B, so "
            f"the editor's index no longer named the row it was opened on: {seen!r}"
        )
        # **And the selection follows the row, not the number** — B moved from index 1 to index 0.
        assert dialog.model.row_at(staging_list(dialog).currentIndex().row()) is kept_b, (
            "the current row became a different URL when a preceding row left the list"
        )
    finally:
        dialog.hide()

    assert dialog.rows == (kept_b, kept_c), "reconciliation did not leave B and C"
    assert isinstance(kept_b.preset, Preset), "B lost the format chosen for it"
    assert kept_b.preset.name == "Audio only (MP3)"
    assert kept_c.preset is None, "the choice made for B was applied to C"

    dialog.add_to_queue()
    committed = dialog.queued_job_ids
    # **Two rows, more than two jobs, and the difference is the playlist** (`T-137`). C enumerates
    # into one job per entry, so the count is 1 + however many the fixture holds. It was `== 2`
    # while the committed capture carried seven *empty* entry objects — the fixture predated the
    # projection reading them, exactly as it predated `fps` and `tbr` (`T-107`'s re-capture).
    # Asserted as a shape rather than a number so a re-capture that changes the entry count does
    # not fail a test about per-row formats.
    assert len(committed) > 2, f"the playlist did not enumerate: {len(committed)} jobs"
    assert store.jobs[committed[0]].request.media_kind is MediaKind.AUDIO, (
        "B was queued with the format it did not ask for"
    )
    assert all(
        store.jobs[job_id].request.media_kind is MediaKind.VIDEO for job_id in committed[1:]
    ), "the choice made for B landed on the following URL"


def test_the_full_selector_survives_a_scaled_font(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`T118-R15`: the row's line budget is fixed, so the *guaranteed* surface must not be.

    The row draws as much of the selector as `SELECTOR_LINES` holds — two lines, which covers the
    longest built-in at the default 9 pt and, as the review measured, **not** at 12 pt and above.
    Sizing the row from the wrapped height would make row height depend on content and cost the
    uniform-row property `T118-R10` turns on, so the contract is narrowed instead: the copyable
    label below the list is what carries the whole value.

    This asserts that at a font where the row provably cannot fit it — the case the previous
    default-font measurement could never have caught.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM)
    label = dialog.findChild(QLabel, "selectorValue")
    assert label is not None

    scaled = QFont(label.font())
    scaled.setPointSize(18)
    label.setFont(scaled)

    selector = preset_registry.effective_selector(dialog.preset_for(dialog.rows[0]))
    metrics = QFontMetrics(scaled)
    # The row's budget at this font, measured the way the delegate lays it out.
    available = RENDER_WIDTH - 2 * PADDING - THUMBNAIL_SIZE[0] - GAP
    needed = metrics.boundingRect(
        QRect(0, 0, available, 10_000),
        int(Qt.TextFlag.TextWordWrap),
        role_values(dialog, SELECTOR_ROLE)[0],
    ).height()
    assert needed > SELECTOR_LINES * metrics.height(), (
        "this font still fits the row, so the test is not exercising the case it names"
    )

    assert selector in label.text(), (
        "the copyable selector is incomplete at a scaled font, which is the one surface that "
        "must always carry the whole value"
    )
    assert label.wordWrap(), "the label cannot grow, so a long selector would clip there too"


def test_the_copyable_selector_follows_the_current_row(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`REQ-009`'s other half: a selector you can *take away*.

    A delegate paints pixels, so the drawn line cannot be selected or copied — and `REQ-009` exists
    so a user can learn the syntax and write their own. The label below the list is the dedicated
    selectable detail, and it follows whichever row is current so a mixed batch can be read one row
    at a time.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM, AUDIO_ONLY)
    choose_in_editor(dialog, open_row_editor(dialog, 1), "Audio only (MP3)")
    listing = staging_list(dialog)

    label = dialog.findChild(QLabel, "selectorValue")
    assert label is not None
    assert label.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse, (
        "the one copyable selector on screen cannot be selected"
    )

    listing.setCurrentIndex(listing.model().index(0, 0))
    first = label.text()
    listing.setCurrentIndex(listing.model().index(1, 0))
    second = label.text()

    assert preset_registry.effective_selector(dialog.preset_for(dialog.rows[0])) in first
    assert preset_registry.effective_selector(dialog.preset_for(dialog.rows[1])) in second
    assert first != second, "the label showed the same selector for two differently-targeted rows"


def superlinear_growth(
    small: Sequence[float], large: Sequence[float], *, headroom: float = SCALING_HEADROOM
) -> str | None:
    """Whether `large` grew faster than `headroom` allows. A message if it did, else `None`.

    **Diagnostic, not a gate** (`P2EXIT-R3`). It is reported and never asserted on: the required
    gates are the 500-row absolute budget and the structural control count, which is what the
    original review recommended and what I talked myself out of.

    Why the ratio cannot be a gate here: each sample builds a manager and a dialog backed by
    `child_never_returning`, and the fixture reaps them only when the test ends. Three pairs plus a
    warm-up therefore leave up to seven managers and their probe workers alive, with every large
    sample running under more background load than the small one before it. **A median cannot
    remove load the harness introduces systematically** — repeating a biased measurement gives a
    reliable biased answer.

    It is kept because the number is worth printing when someone is looking at paste cost. It is
    not kept as a pass/fail claim.
    """
    if len(small) < 2 or len(large) < 2 or len(small) != len(large):
        return f"not enough comparable samples: {len(small)} small, {len(large)} large"
    base, grown = statistics.median(small), statistics.median(large)
    if base <= 0:
        return None
    factor = grown / base
    if factor <= headroom:
        return None
    return (
        f"{SUPPORTED_PASTE} URLs cost {grown:.4f}s against {base:.4f}s for {SMALL_PASTE} — a "
        f"factor of {factor:.1f}, over {headroom}. Medians of {len(small)} pairs: "
        f"small={[round(v, 4) for v in small]}, large={[round(v, 4) for v in large]}"
    )


def test_the_scaling_oracle_ignores_one_stall_and_refuses_a_thin_sample_set() -> None:
    """What the diagnostic promises, asserted against fixed samples.

    Two claims, and the second is new: a single stall must not swing the verdict, **and an
    insufficient or unequal sample set is refused rather than answered**. `P2EXIT-R3` found the
    sample-count contract unguarded — dropping `SCALING_PAIRS` from three to one left this test
    green, because it supplies its own lists and never consulted the constant.
    """
    steady_small = [0.020, 0.021, 0.019]

    for position in range(3):
        stalled = [0.038, 0.041, 0.039]
        stalled[position] = 1.4935
        assert superlinear_growth(steady_small, stalled) is None, (
            f"a stall at position {position} changed the verdict: {stalled}"
        )

    verdict = superlinear_growth(steady_small, [1.40, 1.51, 1.45])
    assert verdict is not None and "factor of 7" in verdict, verdict

    # **The sample set itself is checked**, so one measurement cannot masquerade as a comparison.
    assert "not enough comparable samples" in (superlinear_growth([0.02], [1.40]) or "")
    assert "not enough comparable samples" in (superlinear_growth([0.02, 0.02], [1.40]) or "")

    # **And the live sample count is pinned here, independently** (`P2EXIT-R3`). The tests above
    # supply their own lists, so nothing else in this file notices `SCALING_PAIRS` changing — the
    # review dropped it from three to one and every test stayed green. A median of two is not a
    # median; three is the smallest set where one outlier cannot move it.
    assert SCALING_PAIRS >= 3, (
        f"SCALING_PAIRS is {SCALING_PAIRS}; a stall cannot be outvoted below three samples"
    )


def test_a_four_times_larger_paste_is_reported_and_not_gated(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    qapp: QApplication,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The paste-cost diagnostic. **Nothing here fails the build** (`P2EXIT-R3`).

    Each sample is torn down before the next is timed, which removes the systematic bias the
    review found — but not the shared machine, so the number is evidence to read rather than a
    verdict. `T118-R10`'s load-bearing gates are elsewhere and are required:
    `test_a_paste_the_design_supports_stays_inside_the_interaction_budget` and
    `test_a_large_paste_builds_no_control_at_all_until_one_is_asked_for`.
    """

    def cost(count: int) -> float:
        manager = managers(entry_point=child_never_returning)
        dialog = dialogs(manager)
        urls = "\n".join(f"https://many.invalid/{n}" for n in range(count))
        started = time.monotonic()
        type_urls(dialog, urls)
        dialog.resolve()
        elapsed = time.monotonic() - started
        # **Torn down inside the sample loop, and waited for** (`T122-R2`). Calling `shutdown()`
        # was not enough: it *begins* teardown and returns by design (`T013-R2`), so the previous
        # version resumed timing while the sample it had just finished was still killing four
        # probe workers — and every large sample ran under more of that than the small one before
        # it, which is the systematic bias this loop exists to remove. The wait is outside the
        # timed region, so it costs the diagnostic nothing but wall clock.
        dialog.close()
        manager.shutdown()
        # **The bound is asserted, not merely waited out** (`T122-R2`, second pass), and it waits
        # for the poll timer as well as the work (`T-128`) — `drain` carries both rules, so this
        # sample loop and the fixtures cannot drift about what "finished" means.
        drain(
            qapp,
            [manager],
            describe=lambda: (
                f"This was the {count}-URL sample; every later one would run under its surviving "
                "probe workers, and the diagnostic would report that contamination as paste cost."
            ),
        )
        return elapsed

    cost(SMALL_PASTE)
    small: list[float] = []
    large: list[float] = []
    for pair in range(SCALING_PAIRS):
        # Alternated, so neither size systematically follows the other.
        if pair % 2:
            large.append(cost(SUPPORTED_PASTE))
            small.append(cost(SMALL_PASTE))
        else:
            small.append(cost(SMALL_PASTE))
            large.append(cost(SUPPORTED_PASTE))

    assert len(small) == SCALING_PAIRS and len(large) == SCALING_PAIRS, (
        "the live sample count must follow SCALING_PAIRS; the oracle test cannot police this "
        "because it supplies its own lists"
    )
    reported = superlinear_growth(small, large) or f"within {SCALING_HEADROOM}"
    with capsys.disabled():
        print(f"\npaste cost — {reported}")


# --- 9. the pure helpers, which the rewrite kept ------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", []),
        ("  \n\n  ", []),
        ("https://a.invalid/1", ["https://a.invalid/1"]),
        ("  https://a.invalid/1  ", ["https://a.invalid/1"]),
        (
            "https://a.invalid/1\n\nhttps://b.invalid/2",
            ["https://a.invalid/1", "https://b.invalid/2"],
        ),
        (
            "https://x.invalid/1\nhttps://x.invalid/1",
            ["https://x.invalid/1", "https://x.invalid/1"],
        ),
    ],
)
def test_split_urls_keeps_order_and_duplicates(text: str, expected: list[str]) -> None:
    """`REQ-001`: blank lines are noise, duplicates are not.

    The duplicate case is the one with teeth — deciding two identical lines are one here would
    silently halve a paste, and nothing downstream could tell.
    """
    assert split_urls(text) == expected


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (None, UNKNOWN_TEXT),
        (0, "0:00"),
        (9, "0:09"),
        (61, "1:01"),
        (599, "9:59"),
        (3600, "1:00:00"),
        (3661, "1:01:01"),
        (86399, "23:59:59"),
    ],
)
def test_format_duration_never_invents_a_value(seconds: float | None, expected: str) -> None:
    """`REQ-002`: an unknown duration says so rather than reading as zero.

    yt-dlp genuinely omits a duration for a live stream, and `0:00` for "we do not know" is a
    number the site never sent.
    """
    assert format_duration(seconds) == expected


def test_describe_kind_distinguishes_unknown_length_from_empty() -> None:
    """A playlist nobody has counted is not a playlist of nothing."""
    assert describe_kind(MediaInfo(url="https://a.invalid/x", title="T")) == "Single item"
    assert (
        describe_kind(MediaInfo(url="https://a.invalid/p", title="P", is_playlist=True))
        == "Playlist"
    )
    assert (
        describe_kind(
            MediaInfo(url="https://a.invalid/p", title="P", is_playlist=True, entry_count=42)
        )
        == "Playlist (42 items)"
    )


def test_the_probes_uploader_and_duration_reach_the_durable_row(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """**`T124-R4`.** `UX-005` §3's row anatomy has to hold after the dialog closes.

    §3 names *thumbnail, title, uploader and duration, progress and state* for a row. *(It said
    "in both tabs"; one of the two went with `T-169`/`T-170` — `T-186`.)* The
    staging row drew all of it; `Job` carried the title and the thumbnail and nothing else, so
    everything the probe had learned about *who* and *how long* died with the dialog — and the
    queue, which is the surface the user actually watches, could not render two of the six.
    `T-124`'s task text answered that by narrowing §3 to `REQ-014`'s older field list, which a
    task may not do to an accepted decision.

    Asserted **after `add_to_queue`**, against the row the store actually holds and against the
    recorded fixture rather than against `MediaInfo` — reading the value back out of the probe
    result would compare the pipeline with itself.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM)
    info = load_info(SINGLE_ITEM)
    assert info.get("uploader") and info.get("duration"), (
        f"{SINGLE_ITEM} carries no uploader or duration, so it cannot prove they are carried"
    )

    dialog.add_to_queue()
    assert spin(lambda: not dialog.isVisible())

    committed = dialog.queued_job_ids
    assert len(committed) == 1
    stored = store.jobs[committed[0]]

    assert stored.uploader == info["uploader"], (
        f"the durable row says uploader={stored.uploader!r}; the probe read "
        f"{info['uploader']!r} and UX-005 §3 puts it on the queue row"
    )
    assert stored.duration_seconds == pytest.approx(float(info["duration"])), (
        f"the durable row says duration_seconds={stored.duration_seconds!r}; the probe read "
        f"{info['duration']!r}"
    )


def test_an_unprobed_row_carries_neither_rather_than_a_guess(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    store: FakeStore,
    spin: Callable[..., bool],
) -> None:
    """The other state of `T124-R4`'s pair, and it is the one a default would hide.

    A row the probe learned nothing about must store `None` for both, not `""` and not `0`: a
    zero duration reads as an empty clip and an empty uploader reads as a publisher with no name.
    `MediaInfo` refuses both at construction, and the durable row has to make the same refusal
    rather than filling in for it.
    """
    media = MediaInfo(url=fixture_url(SINGLE_ITEM), title="Nothing else was learned")
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM)
    dialog.rows[0].media = media

    dialog.add_to_queue()
    assert spin(lambda: not dialog.isVisible())

    stored = store.jobs[dialog.queued_job_ids[0]]
    assert stored.uploader is None, f"an unprobed field was stored as {stored.uploader!r}"
    assert stored.duration_seconds is None, (
        f"an unprobed duration was stored as {stored.duration_seconds!r}, which the row would "
        "draw as a real length"
    )


# --- T-137: a playlist becomes one job per entry ----------------------------------------------


def _probed_playlist(dialog: AddUrlDialog, *, title: str, count: int) -> None:
    """Hand the dialog a probe result that enumerated `count` entries."""
    row = dialog.rows[0]
    assert row.job_id is not None
    dialog._on_media_probed(
        row.job_id,
        MediaInfo(
            url=row.url,
            title=title,
            is_playlist=True,
            entry_count=count,
            entries=tuple(
                PlaylistEntry(
                    url=f"https://example.invalid/entry-{index}",
                    title=f"Track {index:02d}",
                    duration_seconds=float(60 + index),
                )
                for index in range(count)
            ),
        ),
    )


def test_a_playlist_is_added_as_one_job_per_entry(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    sink: FakeSink,
    spin: Callable[..., bool],
) -> None:
    """`T-137`: the defect was that a sixteen-item playlist added **one** job and downloaded it.

    `build_options` sets `noplaylist`, so the single job took whichever entry the URL resolved to
    while the staged row said *Playlist (16 items)*. The row told the truth and the queue did not.

    Asserted on what reaches the sink, because that is what becomes durable — `REQ-012` persists
    before anything starts, so a job that is not submitted here never exists.
    """
    dialog = dialogs(managers())
    type_urls(dialog, "https://example.invalid/list")
    dialog.resolve()
    assert spin(lambda: bool(dialog.rows) and dialog.rows[0].job_id is not None)
    _probed_playlist(dialog, title="Trail Sounds", count=4)

    dialog.add_to_queue()
    assert spin(lambda: bool(sink.submissions)), "nothing was submitted"
    submitted = sink.submissions[-1]

    assert len(submitted) == 4, (
        f"a four-entry playlist added {len(submitted)} job(s); the queue does not hold what the "
        "row said the playlist contains"
    )
    assert [job.playlist_index for job in submitted] == [0, 1, 2, 3], (
        "the entries are not indexed in the playlist's own order"
    )
    assert len({job.playlist_id for job in submitted}) == 1, (
        "the entries do not share one playlist id, so nothing groups them"
    )
    assert {job.playlist_title for job in submitted} == {"Trail Sounds"}
    assert [job.url for job in submitted] == [
        f"https://example.invalid/entry-{index}" for index in range(4)
    ], "the jobs point at the playlist URL rather than at its entries"


def test_a_playlists_entries_land_together_in_one_folder(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    sink: FakeSink,
    tmp_path: Path,
    spin: Callable[..., bool],
) -> None:
    """`UX-005` row 10: items that arrived together stay together.

    The title is deliberately hostile — a slash in it would escape the download directory if the
    folder name were interpolated raw, which is the whole reason `sanitize_component` exists.
    """
    dialog = dialogs(managers())
    # The fixture puts every dialog under `tmp_path / "downloads"`; the claim is
    # about where the entries land *relative to it*, so it is read rather than set.
    downloads = tmp_path / "downloads"
    type_urls(dialog, "https://example.invalid/list")
    dialog.resolve()
    assert spin(lambda: bool(dialog.rows) and dialog.rows[0].job_id is not None)
    _probed_playlist(dialog, title="Hill / Bothy: best of", count=2)

    dialog.add_to_queue()
    assert spin(lambda: bool(sink.submissions))
    directories = {Path(job.request.output_directory) for job in sink.submissions[-1]}

    assert len(directories) == 1, f"the entries were scattered across {directories}"
    folder = directories.pop()
    assert folder.parent == downloads, (
        f"the playlist folder {folder} is not inside the download directory; a title with a "
        "separator in it escaped"
    )
    assert folder != downloads, "the entries went straight into the download directory, unfoldered"


def test_a_playlist_nothing_could_enumerate_stays_a_single_job(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    sink: FakeSink,
    spin: Callable[..., bool],
) -> None:
    """`entries` is what *this* extraction materialised, and it can be empty.

    A paginated or partly-unreadable playlist enumerates nothing, and there is then nothing to
    expand into. It downloads as the URL the user pasted — which is what it did before `T-137`.
    """
    dialog = dialogs(managers())
    type_urls(dialog, "https://example.invalid/list")
    dialog.resolve()
    assert spin(lambda: bool(dialog.rows) and dialog.rows[0].job_id is not None)
    row = dialog.rows[0]
    assert row.job_id is not None
    dialog._on_media_probed(
        row.job_id,
        MediaInfo(url=row.url, title="Unenumerable", is_playlist=True, entry_count=9),
    )

    dialog.add_to_queue()
    assert spin(lambda: bool(sink.submissions))
    submitted = sink.submissions[-1]

    assert len(submitted) == 1, f"a playlist with no readable entries added {len(submitted)} jobs"
    assert submitted[0].playlist_id is None, (
        "a job that is not one of several was given a playlist membership, so the queue would "
        "draw a group of one"
    )


# --- T-150: the dialog opens wide enough for the rows it holds ---------------------------------


def opened_viewport_width(dialog: AddUrlDialog) -> int:
    """The viewport width the dialog *asks* to open at.

    **Its `sizeHint`, not its size after `show()`.** The offscreen platform reports an 800 px
    screen and `QWidget::adjustSize` clamps a window to two thirds of one, so `show()` here yields
    533 px whatever the dialog requests — a number about the test platform rather than about the
    dialog. The hint is the dialog's own answer and is what a real screen honours.
    """
    dialog.resize(dialog.sizeHint())
    return staging_list(dialog).viewport().width()


def test_the_dialog_opens_wide_enough_for_a_row_to_keep_its_control(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    qapp: QApplication,
) -> None:
    """`T-150`: the dialog set no size at all, so Qt gave it whatever its hints added up to.

    **Measured before the fix: it opened at 302 px, with a 254 px viewport** — at which
    `_control_rect` had already narrowed the format control to `MIN_CONTROL_WIDTH`. The dialog
    opened with its control at the narrowest it is *allowed* to be, which is what "squeezed by
    accident" means concretely.
    """
    dialog = dialogs(managers())
    dialog.show()
    width = opened_viewport_width(dialog)

    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, width, ROW_HEIGHT)
    option.fontMetrics = QFontMetrics(option.font)
    body = option.rect.adjusted(PADDING, PADDING, -PADDING, -PADDING)
    control = RowDelegate()._control_rect(body, option.fontMetrics.height())

    assert control.width() == EDITOR_WIDTH, (
        f"the dialog opens with a {width}px row, where the format control is drawn "
        f"{control.width()}px wide instead of {EDITOR_WIDTH}; it is already giving way at the "
        "size the dialog chooses for itself"
    )


def test_the_dialog_opens_wide_enough_for_the_selector_it_can_draw(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    qapp: QApplication,
) -> None:
    """`T-150`: `SELECTOR_LINES` holds the longest built-in *given the room to*.

    That constant's promise — "two lines holds the longest built-in at the default 9 pt font" — is
    about a row with the width to keep it, and at the size this dialog used to open the third line
    got 136 px against a selector measuring 962. The widest string is taken from the preset
    catalogue the dialog was actually given, so a dialog built with different presets is sized for
    those.
    """
    dialog = dialogs(managers())
    dialog.show()
    width = opened_viewport_width(dialog)

    body = QRect(0, 0, width, ROW_HEIGHT).adjusted(PADDING, PADDING, -PADDING, -PADDING)
    line = body.right() - (body.left() + THUMBNAIL_SIZE[0] + GAP)
    metrics = QFontMetrics(qapp.font())
    candidates = selector_candidates(preset_registry.BUILT_IN_PRESETS)

    assert candidates, "the preset catalogue produced no selector lines to size the dialog by"
    for text in candidates:
        needed = selector_line_width(metrics, text)
        assert needed <= line, (
            f"the dialog opens with a {line}px format line, and {text!r} needs {needed}px to fit "
            f"in the {SELECTOR_LINES} lines the row gives it"
        )


def test_the_dialog_can_still_be_made_narrower_than_it_opens(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    qapp: QApplication,
) -> None:
    """`T-150`: a **hint**, not a minimum, and the difference is the whole of this test.

    A minimum would open the dialog wide and stop the user narrowing it. Narrow has to keep
    working: `T-135`'s overflow and `T-160`'s narrowing control are what make it safe, and a floor
    would put them out of reach rather than honour them.
    """
    dialog = dialogs(managers())
    dialog.show()
    opens_at = dialog.sizeHint().width()

    dialog.resize(320, dialog.height())

    assert dialog.width() == 320, (
        f"the dialog refused to narrow past {dialog.width()}px, so the width it opens at has "
        "become a floor the user cannot get under"
    )
    assert dialog.minimumSizeHint().width() < opens_at, (
        "the dialog's minimum grew to its opening width, which is the same floor by another route"
    )


def test_a_staged_row_offers_no_verbs_to_drop(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    qapp: QApplication,
) -> None:
    """Why `T-150`'s "no verbs into `⋯`" criterion has nothing to assert here.

    `StagingModel` answers no `VERBS_ROLE`, deliberately: a staged row has no job behind it and
    nothing to act on, and `_verb_rects` documents that drawing a lone `⋯` there would offer a menu
    of nothing. So no width can drop a verb on this surface. Pinned rather than argued in prose,
    because the criterion reads as satisfied either way and only one of the two reasons is true.
    """
    dialog = dialogs(managers())
    type_urls(dialog, "https://example.invalid/one")
    dialog.resolve()
    assert spin(lambda: bool(dialog.rows))

    model = staging_list(dialog).model()
    assert model is not None
    assert model.data(model.index(0, 0), VERBS_ROLE) is None, (
        "a staged row now offers verbs, so T-150's overflow criterion has become live and needs "
        "asserting at the opened width rather than explaining away"
    )


# --- T-108: the format table, opened as the staging row (REQ-008, UX-007's P-1) ---------------


def _probed_with_formats(dialog: AddUrlDialog, formats: tuple[FormatInfo, ...]) -> Row:
    """Resolve row 0 with a probe result carrying `formats`, and hand the row back."""
    row = dialog.rows[0]
    assert row.job_id is not None
    dialog._on_media_probed(
        row.job_id,
        MediaInfo(url=row.url, title="A video with formats", formats=formats),
    )
    QApplication.processEvents()
    return row


def _staged(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    *,
    fixture: str = "derived_format_columns",
    **overrides: Any,
) -> tuple[AddUrlDialog, Row]:
    """A dialog with one resolved row whose formats come from a committed fixture.

    Through the adapter, so the formats under test are the ones a probe would actually produce —
    `has_video`/`has_audio` included, which is the whole basis of the routing.
    """
    dialog = dialogs(managers(), **overrides)
    type_urls(dialog, "https://example.invalid/one")
    dialog.resolve()
    assert spin(lambda: bool(dialog.rows and dialog.rows[0].job_id))
    payload = json.loads((INFODICTS / f"{fixture}.json").read_text(encoding="utf-8"))
    formats = adapter.project_media(payload["info_dict"]).formats
    return dialog, _probed_with_formats(dialog, formats)


def test_choosing_that_entry_opens_the_row_into_the_format_table(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
) -> None:
    """**The whole of `T107-R2`'s re-scoped criterion** (`UX-007`'s `P-1`, `T-108`).

    *The table is reachable from the product*: the control offers the entry, the staging row
    expands to show `T-107`'s widget, and the widget fills the space it is given — asserted on a
    **shown** row, which is how `T107-R2`'s layout defect escaped in the first place.
    """
    dialog, row = _staged(dialogs, managers, spin)
    dialog.show()
    qapp.processEvents()
    try:
        listing = staging_list(dialog)
        before = listing.sizeHintForRow(0)

        control = open_row_editor(dialog, 0)
        choose_in_editor(dialog, control, CHOOSE_FORMATS_DATA)

        panel = dialog.open_format_panel
        assert panel is not None, "the row did not open"
        assert panel.row is row
        assert listing.indexWidget(listing.model().index(0, 0)) is panel, (
            "the panel is not the row; it was placed somewhere else in the dialog"
        )
        assert listing.sizeHintForRow(0) > before, (
            f"the row is still {listing.sizeHintForRow(0)}px, so it did not expand"
        )

        qapp.processEvents()
        table = panel.table
        assert table.width() > 0 and table.height() > 0, "the table was collapsed"
        assert table.table.width() == table.width(), (
            "the view does not fill the widget it was given (T107-R2)"
        )
        assert isinstance(row.media, MediaInfo)
        assert table.model.rowCount() == len(row.media.formats)
    finally:
        dialog.close()


def test_the_open_row_is_the_only_one_that_grows(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
) -> None:
    """Uniform item sizes is a promise an open row breaks, and it must be withdrawn (`T118-R10`).

    Left on, Qt draws **every** row at the open one's height — so a paste of twenty would become a
    column of empty full-height rows the moment one was opened. Asserted with a second row present,
    because with one row the two behaviours are indistinguishable.
    """
    dialog = dialogs(managers())
    type_urls(dialog, "https://example.invalid/one\nhttps://example.invalid/two")
    dialog.resolve()
    assert spin(lambda: len(dialog.rows) == 2 and all(row.job_id for row in dialog.rows))
    payload = json.loads((INFODICTS / "derived_format_columns.json").read_text(encoding="utf-8"))
    formats = adapter.project_media(payload["info_dict"]).formats
    for row in dialog.rows:
        assert row.job_id is not None
        dialog._on_media_probed(row.job_id, MediaInfo(url=row.url, title=row.url, formats=formats))
    QApplication.processEvents()

    listing = staging_list(dialog)
    shut = listing.sizeHintForRow(1)
    control = open_row_editor(dialog, 0)
    choose_in_editor(dialog, control, CHOOSE_FORMATS_DATA)

    assert listing.sizeHintForRow(0) > shut, "the opened row did not grow"
    assert listing.sizeHintForRow(1) == shut, (
        f"the closed row grew to {listing.sizeHintForRow(1)}px with its neighbour"
    )


def test_choosing_one_format_writes_it_as_the_rows_own_request(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
) -> None:
    """`REQ-008`: the chosen id becomes the row's selector, and the row says so (`REQ-009`).

    **What the row says comes from `format_text.format_name`**, which for a selector no built-in
    describes is the literal — so this asserts the sentence the shared naming rule produces rather
    than one this dialog composed (`T140-R3`, `T126-R2` and `T-159` were all that defect).
    """
    dialog, row = _staged(dialogs, managers, spin)
    control = open_row_editor(dialog, 0)
    choose_in_editor(dialog, control, CHOOSE_FORMATS_DATA)
    panel = dialog.open_format_panel
    assert panel is not None

    assert isinstance(row.media, MediaInfo)
    chosen = next(entry for entry in row.media.formats if entry.format_id == "137")
    panel.table.table.setCurrentIndex(
        panel.table.model.index(
            next(
                index
                for index in range(panel.table.model.rowCount())
                if panel.table.model.formats()[index] is chosen
            ),
            0,
        )
    )
    panel.table.choose_current()
    QApplication.processEvents()

    assert isinstance(row.preset, Preset)
    assert row.preset.format_selector == "137"
    assert dialog.open_panel is None, "one format was chosen and the row stayed open"
    assert "137" in item_texts(dialog)[0], item_texts(dialog)[0]


def test_a_chosen_pair_becomes_one_merging_request(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
    sink: FakeSink,
) -> None:
    """`REQ-008`'s subject: *a separate video and audio stream to be merged*, as one job.

    Asserted all the way to the submitted `DownloadRequest`, not to the row: the row is where the
    choice is shown and the request is what runs, and `T118-R8` is what happens when only one of
    the two is checked.
    """
    dialog, row = _staged(dialogs, managers, spin)
    control = open_row_editor(dialog, 0)
    choose_in_editor(dialog, control, CHOOSE_FORMATS_DATA)
    panel = dialog.open_format_panel
    assert panel is not None
    mode = panel.table.mode_control
    assert mode is not None, "the merge mode was not offered for a source that has a pair"
    mode.setChecked(True)

    for format_id in ("137", "140"):
        index = next(
            position
            for position in range(panel.table.model.rowCount())
            if panel.table.model.formats()[position].format_id == format_id
        )
        panel.table.table.setCurrentIndex(panel.table.model.index(index, 0))
        panel.table.choose_current()
    QApplication.processEvents()

    assert dialog.open_panel is None, "the pair completed and the row stayed open"
    assert isinstance(row.preset, Preset)
    assert row.preset.format_selector == "137+140"

    dialog.add_to_queue()
    assert spin(lambda: bool(sink.submissions))
    submitted = sink.submissions[0]
    assert len(submitted) == 1, "a merge became more than one job"
    assert submitted[0].request.format_selector == "137+140"


def test_escape_closes_the_table_and_keeps_the_format_that_was_there_before(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
) -> None:
    """`docs/UX_SPEC.md` §4: *"`Esc` closes, choosing nothing"*.

    **"Nothing" has to mean the row is as it was**, not merely that the widget is gone: leaving the
    selection applied would make `Esc` a confirm with extra steps.

    **Reached through the one route that leaves a written choice on an open panel.** In *one format*
    mode a choice completes the selection and the panel closes itself, so there is no open panel
    left to press `Esc` on — the first version of this test pressed it after the row had already
    closed and passed for that reason. Choosing the video half in *video + audio* and then leaving
    the mode writes `137` to the row while the panel is still open, which is exactly the state
    `Esc` has to undo.
    """
    dialog, row = _staged(dialogs, managers, spin)
    was = dialog.presets[2]
    row.preset = was

    control = open_row_editor(dialog, 0)
    choose_in_editor(dialog, control, CHOOSE_FORMATS_DATA)
    panel = dialog.open_format_panel
    assert panel is not None
    mode = panel.table.mode_control
    assert mode is not None
    mode.setChecked(True)
    index = next(
        position
        for position in range(panel.table.model.rowCount())
        if panel.table.model.formats()[position].format_id == "137"
    )
    panel.table.table.setCurrentIndex(panel.table.model.index(index, 0))
    panel.table.choose_current()
    mode.setChecked(False)
    QApplication.processEvents()
    # **Each read goes into its own local before being compared.** Two identity assertions about
    # the same attribute narrow it to whatever the first one proved, and everything after the
    # second then types as unreachable — the idiom this project already hit once, in the very test
    # that documents it.
    still_open = dialog.open_format_panel
    assert still_open is panel, "the panel closed before Esc could be pressed"
    chosen_instead = row.preset
    assert chosen_instead is not was, "nothing was chosen, so the rest of this proves nothing"

    QTest.keyClick(panel, Qt.Key.Key_Escape)
    QApplication.processEvents()
    closed = dialog.open_format_panel
    assert closed is None, "Esc left the table open"
    restored = row.preset
    assert restored is was, f"Esc kept the choice: the row now runs {restored}"


def test_without_ffmpeg_the_merge_mode_is_not_drawn_and_the_reason_is(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
) -> None:
    """`UX-007`'s `P-13`: not drawn, **and the reason stated where the mode would have been**.

    Both halves are asserted. Hiding the control alone would leave a user looking for a feature the
    documentation describes with nothing on screen to explain its absence, which is the half of the
    ruling that is easy to drop.
    """
    dialog, _row = _staged(dialogs, managers, spin, ffmpeg_available=False)
    control = open_row_editor(dialog, 0)
    choose_in_editor(dialog, control, CHOOSE_FORMATS_DATA)
    panel = dialog.open_format_panel
    assert panel is not None

    assert panel.table.mode_control is None, "the merge mode was drawn without ffmpeg"
    stated = panel.findChild(QLabel, "mergeModeUnavailable")
    assert stated is not None, "the mode is gone and nothing says why"
    assert "ffmpeg" in stated.text()


def test_a_source_with_no_pair_says_so_rather_than_blaming_ffmpeg(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
) -> None:
    """Two different impossibilities need two different sentences (`UX-005` §5, derived).

    Every recorded source publishes complete files only, so *video + audio* on one can never be
    completed. Telling that user to install ffmpeg would send them to fix something that is not the
    problem.
    """
    dialog, _row = _staged(dialogs, managers, spin, fixture="wikimedia_caminandes")
    control = open_row_editor(dialog, 0)
    choose_in_editor(dialog, control, CHOOSE_FORMATS_DATA)
    panel = dialog.open_format_panel
    assert panel is not None

    assert panel.table.mode_control is None
    stated = panel.findChild(QLabel, "mergeModeUnavailable")
    assert stated is not None
    assert "ffmpeg" not in stated.text(), (
        f"a source with no pair was blamed on ffmpeg: {stated.text()!r}"
    )
    assert "no separate video and audio" in stated.text()


def test_a_stated_merge_is_refused_before_the_download_when_ffmpeg_goes_missing(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
    sink: FakeSink,
) -> None:
    """`REQ-024`: named, and **before** anything is queued — not at merge time.

    `P-13` means this normally cannot be reached, so the state is constructed the way it would
    actually arise: the pair is chosen with ffmpeg present and ffmpeg is then gone by the time Add
    is pressed. The refusal names the row, because a batch needs to say which one.
    """
    dialog, row = _staged(dialogs, managers, spin)
    control = open_row_editor(dialog, 0)
    choose_in_editor(dialog, control, CHOOSE_FORMATS_DATA)
    panel = dialog.open_format_panel
    assert panel is not None
    mode = panel.table.mode_control
    assert mode is not None
    mode.setChecked(True)
    for format_id in ("137", "140"):
        index = next(
            position
            for position in range(panel.table.model.rowCount())
            if panel.table.model.formats()[position].format_id == format_id
        )
        panel.table.table.setCurrentIndex(panel.table.model.index(index, 0))
        panel.table.choose_current()
    QApplication.processEvents()

    dialog._ffmpeg_available = False
    dialog.add_to_queue()
    QApplication.processEvents()

    assert sink.submissions == [], "a merge without ffmpeg reached the queue"
    message = text_of(dialog, "statusMessage")
    assert "ffmpeg" in message, message
    assert headline_text(row) in message, f"the refusal does not say which row: {message!r}"


def test_a_single_choice_still_queues_without_ffmpeg(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
    sink: FakeSink,
) -> None:
    """**`T-061`, in the direction it actually failed** (`docs/UX_SPEC.md` §5).

    The gate that broke refused a download it could have performed: `bestvideo+bestaudio/best`
    against a source offering one progressive format resolves through `/best` to no merge, and a
    selector-reading check refused it anyway. The format chosen here is `137` — one half of the
    `137+140` pair — so a refusal that had drifted into scanning ids or selectors has something to
    catch on, and the criterion above passes while this one fails.
    """
    dialog, _row = _staged(dialogs, managers, spin, ffmpeg_available=False)
    control = open_row_editor(dialog, 0)
    choose_in_editor(dialog, control, CHOOSE_FORMATS_DATA)
    panel = dialog.open_format_panel
    assert panel is not None
    index = next(
        position
        for position in range(panel.table.model.rowCount())
        if panel.table.model.formats()[position].format_id == "137"
    )
    panel.table.table.setCurrentIndex(panel.table.model.index(index, 0))
    panel.table.choose_current()
    QApplication.processEvents()

    dialog.add_to_queue()
    assert spin(lambda: bool(sink.submissions)), (
        f"a single chosen format was refused without ffmpeg: {text_of(dialog, 'statusMessage')!r}"
    )
    assert sink.submissions[0][0].request.format_selector == "137"


# --- T108-R2: an open panel survives the URL list changing under it ---------------------------


def _two_resolved_rows(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    urls: str,
) -> AddUrlDialog:
    """A dialog whose every pasted line has resolved, with formats on each."""
    dialog = dialogs(managers())
    type_urls(dialog, urls)
    dialog.resolve()
    count = len(urls.split())
    assert spin(lambda: len(dialog.rows) == count and all(row.job_id for row in dialog.rows))
    payload = json.loads((INFODICTS / "derived_format_columns.json").read_text(encoding="utf-8"))
    formats = adapter.project_media(payload["info_dict"]).formats
    for row in dialog.rows:
        assert row.job_id is not None
        dialog._on_media_probed(row.job_id, MediaInfo(url=row.url, title=row.url, formats=formats))
    QApplication.processEvents()
    return dialog


def _open_the_table(dialog: AddUrlDialog, index: int) -> FormatPanel:
    """Open one row's format table through the control, and wait for it to be mounted.

    The mount is deferred by one event-loop turn (`T108-R2`): Qt keeps index widgets and item
    editors in one map, so mounting while the combo box is still open destroys it under the
    delegate. Draining here rather than in every caller.
    """
    control = open_row_editor(dialog, index)
    choose_in_editor(dialog, control, CHOOSE_FORMATS_DATA)
    QApplication.processEvents()
    panel = dialog.open_format_panel
    assert panel is not None, f"row {index} did not open into its format table"
    return panel


def _mounted_on(dialog: AddUrlDialog, row: Row, panel: FormatPanel) -> bool:
    """Whether `panel` is actually the index widget of `row`'s current index.

    **The panel is passed in rather than read from the dialog.** Comparing against
    `dialog.open_panel` made the helper answer `True` once both were `None` — so "is it still
    mounted?" said yes about a row with no widget and a dialog with no panel, which is exactly the
    question this exists to answer.
    """
    listing = staging_list(dialog)
    model = listing.model()
    assert model is not None
    for position in range(model.rowCount()):
        if dialog.model.row_at(position) is row:
            return listing.indexWidget(model.index(position, 0)) is panel
    return False


@pytest.mark.parametrize(
    ("started", "retyped", "case"),
    [
        (
            "https://example.invalid/one\nhttps://example.invalid/two",
            "https://example.invalid/two\nhttps://example.invalid/one",
            "reordering the lines",
        ),
        (
            "https://example.invalid/one\nhttps://example.invalid/two",
            "https://example.invalid/one\nhttps://example.invalid/two\nhttps://example.invalid/3",
            "adding a line",
        ),
        (
            "https://example.invalid/one\nhttps://example.invalid/two",
            "https://example.invalid/one",
            "removing the other line",
        ),
    ],
)
def test_the_open_format_table_survives_the_url_list_changing(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
    started: str,
    retyped: str,
    case: str,
) -> None:
    """`T108-R2`: a structural reset must not orphan the panel.

    A reset drops the index widget, and `_expanded`/`_panel` kept pointing at the row anyway — so
    the row stayed **tall and blank**, and reopening it returned early because it was still "the
    expanded one". Every case here is an ordinary thing to do while choosing a format.

    **Remounted by identity, never by position**: reconciling A/B to B/A leaves row 0 valid and
    meaning a different URL, so a positional remount would hang one row's table under another's.
    """
    dialog = _two_resolved_rows(dialogs, managers, spin, started)
    first = dialog.rows[0]
    panel = _open_the_table(dialog, 0)
    assert _mounted_on(dialog, first, panel)

    type_urls(dialog, retyped)
    dialog.resolve()
    QApplication.processEvents()

    assert dialog.open_panel is panel, f"{case} closed the panel"
    assert panel.row is first, f"{case} moved the panel to another row"
    assert _mounted_on(dialog, first, panel), (
        f"{case} left the panel orphaned: the row is expanded and carries no widget"
    )

    # **The reviewer's exact second symptom.** Asking to open the row again returns early because
    # it *is* the expanded one — which is right only if it is also still mounted. Orphaned, that
    # early return was what made the blank row permanent: closing was the only way out and nothing
    # offered it.
    dialog.open_format_table(first)
    QApplication.processEvents()
    assert dialog.open_panel is panel
    assert _mounted_on(dialog, first, panel), (
        f"after {case}, reopening the row left it expanded and blank"
    )


def test_a_row_whose_line_is_deleted_takes_its_open_table_with_it(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
) -> None:
    """The one case that cannot be remounted: the row itself is gone.

    Closing rather than remounting somewhere plausible — there is nowhere plausible. `keep=True`
    because the selection was written to the row when it was made, and the row is what left.
    """
    dialog = _two_resolved_rows(
        dialogs,
        managers,
        spin,
        "https://example.invalid/one\nhttps://example.invalid/two",
    )
    _open_the_table(dialog, 0)

    type_urls(dialog, "https://example.invalid/two")
    dialog.resolve()
    QApplication.processEvents()

    assert dialog.open_panel is None, "the panel outlived the row it belonged to"


def test_the_same_row_can_open_its_table_again_after_a_reset(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
) -> None:
    """`T108-R2`'s second half: the row could never be reopened once orphaned.

    `open_format_table` returns early when the row is already the expanded one — correct, and it
    made the blank row permanent, because closing was the only way out and nothing offered it.
    Asserted after a close as well as after a reset, so the early return is exercised in the state
    it is meant for.
    """
    dialog = _two_resolved_rows(
        dialogs,
        managers,
        spin,
        "https://example.invalid/one\nhttps://example.invalid/two",
    )
    first = dialog.rows[0]
    opened = _open_the_table(dialog, 0)

    type_urls(dialog, "https://example.invalid/two\nhttps://example.invalid/one")
    dialog.resolve()
    QApplication.processEvents()

    dialog.close_panel(keep=True)
    assert dialog.open_panel is None
    assert not _mounted_on(dialog, first, opened), "the closed panel is still the row's widget"

    position = next(
        index for index in range(len(dialog.model.shown)) if dialog.model.shown[index] is first
    )
    reopened = _open_the_table(dialog, position)
    assert reopened.row is first, "reopening after a reset landed on a different row"
    assert _mounted_on(dialog, first, reopened)


def test_choosing_the_options_entry_opens_the_editor_and_keeps_the_row_s_format(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sentinel must reach `open_options` and **not** the preset lookup (`T-109`).

    `setData` looks any string up as a preset name and writes the answer onto the row, so a
    sentinel that fell through would find nothing and silently clear the format the user chose —
    a wrong download rather than a no-op. Asserted on the row rather than only on the call,
    because the call being made does not by itself mean the lookup was skipped.
    """
    dialog, row = _staged(dialogs, managers, spin)
    row.preset = preset_registry.AUDIO_MP3
    opened: list[Row] = []
    monkeypatch.setattr(type(dialog), "open_options", lambda _self, r: opened.append(r))

    index = dialog.model.index(0, 0)
    assert dialog.model.setData(index, OPTIONS_DATA, PRESET_ROLE)

    assert opened == [row]
    assert row.preset is preset_registry.AUDIO_MP3, (
        "the sentinel reached the preset lookup and cleared the row's chosen format"
    )


# --- T-110: the playlist picker, opened as the staging row (REQ-004, UX-007's P-19) -----------
#
# The picker widget itself is `tests/ui/test_playlist_picker.py`; the selection rules are
# `tests/unit/test_playlist_selection.py`. What is asserted here is what the **dialog** does with
# them — which row opens, what the row says, and above all *what reaches the queue*, because
# `REQ-004` is a claim about what gets enqueued and not about what a checkbox looks like.


def _staged_playlist(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    **overrides: Any,
) -> tuple[AddUrlDialog, Row]:
    """A dialog holding one resolved row whose probe was a real seven-entry playlist.

    Through the recorded extraction and the real adapter, so the entries under test are the ones a
    probe actually produces — `T-137` recorded this fixture for exactly that.
    """
    dialog, _manager = resolved(dialogs, managers, spin, PLAYLIST, **overrides)
    row = dialog.rows[0]
    media = row.media
    assert isinstance(media, MediaInfo) and len(media.entries) == 7, (
        f"{PLAYLIST} did not resolve into entries to choose between: {media}"
    )
    return dialog, row


def _open_the_picker(dialog: AddUrlDialog, row: Row) -> Any:
    """Open one row's playlist picker and wait for the deferred mount (`T108-R2`'s ordering)."""
    dialog.open_playlist_picker(row)
    QApplication.processEvents()
    panel = dialog.open_playlist_panel
    assert panel is not None, "the row did not open into its playlist picker"
    return panel


def _expanded_role_of(dialog: AddUrlDialog, row: Row) -> object:
    """What the model answers for `row`'s disclosure — the value the delegate paints from."""
    index = dialog._model.index(dialog.rows.index(row), 0)
    return dialog._model.data(index, EXPANDED_ROLE)


def test_a_row_that_left_the_queue_can_still_close_its_picker(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """**`T-204`.** The panel must not outlive the control that dismisses it.

    The maintainer's report: *"I think it removed the video from being downloaded, but it made
    everything inaccessible."* `EXPANDED_ROLE` answered `None` — which `T-140` defines as *not a
    playlist, draw no disclosure* — for **any** row that was not `committable`, and `RowDelegate`
    both **paints** the triangle and **hit-tests the click** on `isinstance(..., bool)`. So the
    affordance and the target under it went at once, while the panel stayed mounted.

    **Every step is a route a user can reach** (`T204-R1`). The picker opens through
    `open_playlist_picker`; an entry is unchecked with `Space`, which is the gesture the report
    describes; the row stops being committable because **its job left the queue** —
    `manager.job_changed` with a status that is not startable, which `_on_job_changed` turns into
    `FAILED`; and the panel is closed through `toggle_playlist`, the slot the delegate's disclosure
    signal is wired to.

    *(An earlier version assigned `PROBING` to a `READY` row directly. `T204-R1` found that
    production only reaches `PROBING` from `WAITING`, so that test proved the role's invariant and
    not the reported defect.)*
    """
    dialog, manager = resolved(dialogs, managers, spin, PLAYLIST)
    row = dialog.rows[0]
    panel = _open_the_picker(dialog, row)
    assert isinstance(_expanded_role_of(dialog, row), bool), (
        "an open playlist row did not offer a disclosure before anything changed"
    )

    # Uncheck one entry, the way the report describes — `Space` on the picker's current row.
    QTest.keyClick(panel.picker.table, Qt.Key.Key_Space)
    QApplication.processEvents()
    chosen = row.entry_selection
    assert isinstance(chosen, PlaylistSelection) and len(chosen.checked) == 6, (
        f"the keystroke did not uncheck exactly one entry: {chosen}"
    )

    job_id = row.job_id
    assert isinstance(job_id, str) and job_id
    manager.job_changed.emit(job_id, JobStatus.CANCELLED.value)
    QApplication.processEvents()

    assert row.state is RowState.FAILED and not row.committable, (
        f"the job leaving the queue did not make the row uncommittable: {row.state}"
    )
    assert dialog.open_panel is panel, "the panel closed on its own; this asserts the wrong thing"
    assert isinstance(_expanded_role_of(dialog, row), bool), (
        "the row kept its panel and stopped offering a disclosure, so the only way out of the "
        "picker is cancelling the dialog — the panel outlived the control that dismisses it"
    )

    # **Closed by pressing the control the user has** (`T204-R1`). Calling `toggle_playlist` was
    # calling the receiving slot, which proves the slot and not the route. While a panel is open
    # `setIndexWidget` covers the row's disclosure, so the panel's own *Done* button is the pointer
    # route out — and it is the one the report says was missing.
    assert panel is not None
    panel.done_button.click()
    QApplication.processEvents()

    assert dialog.open_panel is None, "the panel's own Done button did not close it"
    assert row.entry_selection == chosen, (
        f"closing discarded the choice made in the picker: {row.entry_selection} != {chosen}"
    )


def test_an_open_playlist_keeps_its_disclosure_when_another_url_joins_the_batch(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """**`T-204`, the second report**: *"with multiple items in the queue, the playlist loses the
    arrow to collapse it again."*

    Adding a line reconciles the staging list, which is a **structural reset** — `T108-R2`'s case.
    The panel is dropped and remounted by row identity, and every row is re-asked for its
    disclosure while the new row is still resolving.

    **This is a guard, not a reproduction, and the difference is worth stating.** It passes with
    the fix and *without* it: a playlist row stays `READY` while a sibling resolves, so the
    committable gate never fired on the path this test drives. **The reported condition — more
    than one item — does not by itself remove the arrow.** The likely explanation is that with
    several rows a re-probe is simply common, and a re-probing row is the case
    `test_a_row_that_stops_being_committable_can_still_close_its_panel` reproduces and the fix
    closes. **The exact gesture behind the second report remains unconfirmed**, and this test
    exists so that the multi-row path cannot regress into it.
    """
    dialog, row = _staged_playlist(dialogs, managers, spin)
    panel = _open_the_picker(dialog, row)

    type_urls(dialog, f"{row.url}\n{fixture_url(SINGLE_ITEM)}")
    dialog.resolve()
    assert spin(lambda: len(dialog.rows) > 1 and all(s in SETTLED for s in states(dialog))), (
        f"the second URL never settled into a row: {states(dialog)}"
    )
    QApplication.processEvents()

    assert dialog.open_panel is panel, "the reconcile dropped the panel it should have remounted"
    assert dialog.rows[0] is row, "the playlist row was replaced rather than kept across the paste"
    assert isinstance(_expanded_role_of(dialog, row), bool), (
        "the open playlist lost its disclosure once a second row joined the batch; there is no "
        "way to collapse it"
    )


def test_removing_a_row_above_keeps_the_open_panels_way_back_on_screen(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    qapp: QApplication,
    spin: Callable[..., bool],
) -> None:
    """**`T-208`: a reproduced multi-row route that loses the arrow** — and its fix.

    With a row above and a row below, an open playlist fills the viewport and the list is
    scrolled. Removing the row above shrinks the scroll range; Qt keeps the *offset*, so the
    surviving row — panel and all — slides up until its top is above the fold **and stays
    there**: fifty event-loop turns do not move it back. The collapse control lives at that top,
    and an open row's twisty is deliberately not painted (`T-210`'s one-arrow rule), so the
    removal has quietly taken the arrow with it. `remount_panel` now re-anchors the row's top
    into view exactly when it left.

    **This is one reproduced route, not a claim about the maintainer's report.** The exact
    gesture behind *"with multiple items … the playlist loses the arrow"* is still theirs to
    confirm; what this pins is that this route existed, is fixed, and cannot come back — with
    the selection surviving the close, which is the criterion's second half.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM, PLAYLIST)
    dialog.resize(900, 700)
    dialog.show()
    try:
        qapp.processEvents()
        playlist = dialog.rows[1]
        panel = _open_the_picker(dialog, playlist)
        qapp.processEvents()

        # A choice the close must keep: `Space` on the picker's current entry, the real gesture.
        QTest.keyClick(panel.picker.table, Qt.Key.Key_Space)
        qapp.processEvents()
        chosen = playlist.entry_selection
        assert isinstance(chosen, PlaylistSelection) and len(chosen.checked) == 6

        # A third row below, so the scroll range stays real once the first row goes.
        existing = "\n".join(fixture_url(name) for name in (SINGLE_ITEM, PLAYLIST))
        type_urls(dialog, existing + "\n" + fixture_url(AUDIO_ONLY))
        dialog.resolve()
        assert spin(lambda: len(dialog.rows) == 3 and all(s in SETTLED for s in states(dialog)))
        qapp.processEvents()

        dialog.remove_row(dialog.rows[0])
        qapp.processEvents()

        viewport = staging_list(dialog).viewport()
        collapse = panel.collapse_button
        top = collapse.mapTo(viewport, collapse.rect().topLeft()).y()
        assert 0 <= top <= viewport.height(), (
            f"after the removal the collapse control sits at y={top} in a "
            f"{viewport.height()}px viewport — the arrow left the screen and stayed gone"
        )

        collapse.click()
        qapp.processEvents()
        assert dialog.open_panel is None, "the way back did not close the panel"
        assert playlist.entry_selection == chosen, (
            f"closing discarded the choice made before the removal: "
            f"{playlist.entry_selection} != {chosen}"
        )
    finally:
        dialog.close()


def test_a_playlist_row_offers_a_disclosure_and_a_single_item_does_not(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`EXPANDED_ROLE` is three-valued, and *absent* is what a single item answers (`T-140`).

    Absent draws no triangle at all; `False` draws a closed one. A single-video row answering
    `False` would offer to open something that has nothing in it — `UX-005` §5 — and is also
    `T-110`'s last criterion, that a single-video URL behaves exactly as it does today.
    """
    dialog, _manager = resolved(dialogs, managers, spin, SINGLE_ITEM, PLAYLIST)

    assert role_values(dialog, EXPANDED_ROLE) == [None, False], (
        "the single item drew a disclosure, or the playlist did not"
    )


def test_the_disclosure_opens_the_playlist_as_the_row_itself(
    qapp: QApplication,
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`P-19`: the picker is the staging list's own row, opened — not a separate dialog.

    Asserted as *the panel is the row's index widget*, which is the same property `T107-R2`'s
    criterion was re-scoped to, and the only one that distinguishes a row that opens from a window
    that appears next to it.
    """
    dialog, row = _staged_playlist(dialogs, managers, spin)
    dialog.show()
    qapp.processEvents()
    try:
        listing = staging_list(dialog)
        before = listing.sizeHintForRow(0)

        dialog.toggle_playlist(str(row.job_id))
        qapp.processEvents()

        panel = dialog.open_playlist_panel
        assert panel is not None, "the disclosure did not open the row"
        assert panel.row is row
        assert listing.indexWidget(listing.model().index(0, 0)) is panel, (
            "the picker was placed somewhere other than on the row (P-19)"
        )
        assert listing.sizeHintForRow(0) > before, "the row did not expand"
        assert panel.picker.model.rowCount() == 7
        assert dialog.findChild(QDialog, "playlistPicker") is None, (
            "the picker is a dialog, which is the modal-over-a-modal UX-007 ruled against"
        )
    finally:
        dialog.close()


def test_the_arrow_keys_open_and_close_the_playlist(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`docs/UX_SPEC.md` §7's own keyboard row, pressed on the list rather than called.

    A route that needs a pointer first is not a route (`T-152`), so this presses the keys on the
    staging list with the row merely current — which is where `Tab` leaves a keyboard user.
    """
    dialog, row = _staged_playlist(dialogs, managers, spin)
    listing = staging_list(dialog)
    listing.setCurrentIndex(dialog.model.index(0, 0))

    QTest.keyClick(listing, Qt.Key.Key_Right)
    QApplication.processEvents()
    assert dialog.open_playlist_panel is not None, "`→` did not open the playlist"

    QTest.keyClick(listing, Qt.Key.Key_Left)
    QApplication.processEvents()
    assert dialog.open_panel is None, "`←` did not close the playlist"
    assert row.entry_selection is not None, "closing threw the row's choice away"


def test_the_arrow_key_opens_nothing_on_a_row_that_is_not_a_playlist(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`UX-005` §5: the key exists on every row, and it must not open an empty picker."""
    dialog, _manager = resolved(dialogs, managers, spin, SINGLE_ITEM)
    listing = staging_list(dialog)
    listing.setCurrentIndex(dialog.model.index(0, 0))

    QTest.keyClick(listing, Qt.Key.Key_Right)
    QApplication.processEvents()

    assert dialog.open_panel is None, "a single item opened into a playlist picker"


def test_only_the_chosen_entries_become_jobs(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    sink: FakeSink,
    store: FakeStore,
) -> None:
    """**`T-110`'s subject**, asserted on the stored queue rather than on the picker.

    `REQ-004` is a claim about what gets enqueued. A test that read the checkboxes back would pass
    with `_durable_jobs` ignoring them entirely, which is the whole defect this exists to prevent.
    """
    dialog, row = _staged_playlist(dialogs, managers, spin)
    panel = _open_the_picker(dialog, row)
    media = row.media
    assert isinstance(media, MediaInfo)

    panel.picker.model.clear_selection()
    panel.picker.model.set_checked((1, 4), True)
    QApplication.processEvents()

    dialog.add_to_queue()
    assert spin(lambda: bool(sink.submissions))

    stored = [job for job in store.jobs.values() if job.playlist_id is not None]
    assert [job.url for job in stored] == [media.entries[1].url, media.entries[4].url], (
        "the queue holds entries the user did not choose, or is missing ones they did"
    )
    assert [job.playlist_index for job in stored] == [1, 4], (
        "the chosen entries were renumbered, so the queue's record of the playlist disagrees "
        "with the playlist"
    )


def test_the_whole_selection_is_submitted_as_one_batch(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    sink: FakeSink,
) -> None:
    """`T-110`: *the whole selection is appended in one transaction*.

    The atomicity itself is `JobRepository.append`'s and is proven at
    `tests/unit/test_persistence.py::test_append_writes_every_job_or_none_of_them` — a kill
    mid-append leaves none, not some. What this task had to do was **use** it rather than loop, so
    what is asserted here is the property that reaches it: one `submit`, carrying every chosen
    entry. A loop of one-job submissions would be five transactions and five chances to stop
    halfway.
    """
    dialog, row = _staged_playlist(dialogs, managers, spin)
    panel = _open_the_picker(dialog, row)
    panel.picker.model.set_checked((0, 6), False)
    QApplication.processEvents()

    dialog.add_to_queue()
    assert spin(lambda: bool(sink.submissions))

    assert len(sink.submissions) == 1, (
        f"{len(sink.submissions)} submissions: the entries were appended one at a time, so a "
        "crash could leave half a playlist queued"
    )
    assert len(sink.submissions[0]) == 5


def test_nothing_downloads_until_the_user_confirms(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    store: FakeStore,
) -> None:
    """`REQ-004` is explicit: *before any download starts*.

    Probing, opening the picker and changing the choice must all leave the queue empty. Asserted
    on the store, because that is where a job that had started would have had to be written first
    (`REQ-012`).
    """
    dialog, row = _staged_playlist(dialogs, managers, spin)
    panel = _open_the_picker(dialog, row)
    panel.picker.model.set_checked((2,), False)
    QApplication.processEvents()

    assert store.jobs == {}, "something reached the queue before Add was pressed"
    assert dialog.queued_job_ids == ()


def test_the_row_says_how_much_of_its_playlist_is_chosen(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`UX-003`: the staging list is where the batch is read, so the choice has to appear on it.

    Otherwise the only place it exists is inside the picker, and a user who closed the row cannot
    see what Add is about to queue.
    """
    dialog, row = _staged_playlist(dialogs, managers, spin)

    assert "all chosen" in item_texts(dialog)[0], item_texts(dialog)[0]

    panel = _open_the_picker(dialog, row)
    panel.picker.model.set_checked((0, 1, 2), False)
    QApplication.processEvents()

    assert "4 chosen" in item_texts(dialog)[0], item_texts(dialog)[0]


def test_a_playlist_nobody_opened_still_queues_every_entry(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    sink: FakeSink,
) -> None:
    """The default, and the reason it is the default: doing nothing must not drop the playlist.

    This is `T-137`'s behaviour unchanged, which is what makes the picker an addition rather than
    a new way to lose a download.
    """
    dialog, _row = _staged_playlist(dialogs, managers, spin)

    dialog.add_to_queue()
    assert spin(lambda: bool(sink.submissions))

    assert len(sink.submissions[0]) == 7


def test_a_playlist_with_nothing_chosen_says_so_instead_of_adding_nothing(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    sink: FakeSink,
) -> None:
    """An empty batch would submit successfully, close the dialog and add **nothing**.

    The user's choice honoured and their whole paste silently discarded, which is the failure mode
    a filter introduces. Said instead, with the batch left on screen.
    """
    dialog, row = _staged_playlist(dialogs, managers, spin)
    panel = _open_the_picker(dialog, row)
    panel.picker.model.clear_selection()
    QApplication.processEvents()

    dialog.add_to_queue()
    QApplication.processEvents()

    assert sink.submissions == [], "an empty selection reached the writer"
    assert dialog.result() != QDialog.DialogCode.Accepted, (
        "the dialog accepted and closed having added nothing"
    )
    message = text_of(dialog, "statusMessage")
    assert "Nothing is chosen" in message, message


def test_a_single_video_url_still_becomes_exactly_one_job(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    sink: FakeSink,
) -> None:
    """`T-110`'s last criterion, asserted rather than assumed.

    The filter runs on every commit, so the case it must not touch is the common one: a pasted
    video is one job carrying the URL the user pasted, with no playlist membership at all.
    """
    dialog, _manager = resolved(dialogs, managers, spin, SINGLE_ITEM)

    dialog.add_to_queue()
    assert spin(lambda: bool(sink.submissions))

    submitted = sink.submissions[0]
    assert len(submitted) == 1
    assert submitted[0].url == fixture_url(SINGLE_ITEM)
    assert submitted[0].playlist_id is None and submitted[0].playlist_index is None


def test_reopening_a_playlist_shows_the_choice_that_was_made(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`P-19` makes the picker a row that opens and closes, so closing must not be a reset."""
    dialog, row = _staged_playlist(dialogs, managers, spin)
    panel = _open_the_picker(dialog, row)
    panel.picker.model.set_checked((3, 5), False)
    QApplication.processEvents()
    dialog.close_panel(keep=True)

    reopened = _open_the_picker(dialog, row)

    assert sorted(reopened.picker.selection.checked) == [0, 1, 2, 4, 6]


def test_escape_puts_the_earlier_choice_back(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`Esc` *closes, choosing nothing* — and the row's entry selection is what "nothing" is here.

    The undo is supplied by whichever `open_…` built the panel, because a close that restored the
    row's *preset* as well would send a playlist row back to inheriting a format it had chosen.
    """
    dialog, row = _staged_playlist(dialogs, managers, spin)
    row.preset = preset_registry.AUDIO_MP3
    panel = _open_the_picker(dialog, row)
    before = row.entry_selection
    panel.picker.model.clear_selection()
    QApplication.processEvents()
    assert row.entry_selection != before, "the picker's change never reached the row"

    dialog.close_panel(keep=False)

    assert row.entry_selection == before, "Esc kept the choice it was supposed to discard"
    assert row.preset is preset_registry.AUDIO_MP3, (
        "closing the playlist picker also reverted the row's format"
    )


def test_a_reprobe_of_a_different_length_starts_the_choice_again(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """Positions belong to one extraction (`PlaylistSelection.with_count`).

    A retry can return a shorter playlist, and keeping whichever indices still fit would present a
    choice the user never made over items they have not seen.
    """
    dialog, row = _staged_playlist(dialogs, managers, spin)
    media = row.media
    assert isinstance(media, MediaInfo)
    dialog._on_entries_chosen(row, PlaylistSelection.none_of(7).set(6, True))

    assert row.job_id is not None
    dialog._on_media_probed(
        row.job_id,
        MediaInfo(
            url=media.url,
            title=media.title,
            is_playlist=True,
            entries=media.entries[:3],
        ),
    )
    QApplication.processEvents()

    assert row.entry_selection == PlaylistSelection.all_of(3)


def test_a_large_playlist_probe_leaves_the_dialog_responsive_and_cancellable(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`NFR-001`, `REQ-027`: a hundred-entry extraction is long, and the dialog must not wait.

    **The child never answers**, which is the only shape that can prove the dialog is not blocked
    on it: the assertions below all run while a real worker process is still extracting. Removing
    the row then stops that process, which is what *cancellable* means here — there is nothing
    durable to withdraw, because a staging probe never wrote a row (`T118-R1`).
    """
    manager = managers(entry_point=child_never_returning)
    dialog = dialogs(manager)
    type_urls(dialog, "https://example.invalid/a-very-long-playlist")
    dialog.resolve()
    assert spin(lambda: bool(dialog.rows and dialog.rows[0].job_id))
    row = dialog.rows[0]
    probing = row.job_id
    assert probing is not None

    # The GUI thread is free: the dialog answers, repaints and edits while the probe runs.
    assert spin(lambda: row.state in (RowState.WAITING, RowState.PROBING))
    assert dialog.status_text(), "the dialog stopped saying anything while a probe ran"
    type_urls(dialog, "https://example.invalid/a-very-long-playlist\nhttps://example.invalid/two")
    dialog.resolve()
    assert len(dialog.rows) == 2, "the dialog could not accept another line mid-probe"

    dialog.remove_row(row)

    assert spin(lambda: probing not in manager.active_job_ids()), (
        "the probe outlived the row it belonged to, so a long playlist cannot be cancelled"
    )


# --- T-112: the output template editor and its live preview (REQ-011, UX_SPEC §9.1) ------------
#
# The widget is `tests/ui/test_template_editor.py`, the field set is
# `tests/unit/test_output_template.py`, the containment is `tests/unit/test_paths.py`, and the
# preview equalling the written path is `tests/integration/test_end_to_end.py`. What is here is the
# **dialog**: that the editor is reachable, that the preview is live, and — the one that matters —
# that a refused template never becomes a request.


def _open_the_template_editor(dialog: AddUrlDialog, index: int = 0) -> Any:
    """Open one row's template editor through the control, and wait for the deferred mount."""
    control = open_row_editor(dialog, index)
    choose_in_editor(dialog, control, TEMPLATE_DATA)
    QApplication.processEvents()
    panel = dialog.open_template_panel
    assert panel is not None, f"row {index} did not open into its template editor"
    return panel


def test_the_editor_opens_showing_the_template_the_row_already_has(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
) -> None:
    """A preview that appears only once you type makes the user prove the feature before it helps.

    The interesting question is *what does the template I already have produce* — so the panel
    opens with the row's own template in the input and a path already under it.
    """
    dialog, row = _staged(dialogs, managers, spin)
    panel = _open_the_template_editor(dialog)

    assert panel.row is row
    assert panel.editor.template == preset_registry.DEFAULT_OUTPUT_TEMPLATE
    assert panel.editor.preview_text().endswith("A video with formats.ext"), (
        panel.editor.preview_text()
    )
    assert panel.editor.preview_text().startswith(str(dialog._output_directory))


def test_the_preview_follows_every_keystroke(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
) -> None:
    """`REQ-011`'s *live* preview, driven by typing rather than by calling the slot (`P-23`)."""
    dialog, _row = _staged(dialogs, managers, spin)
    panel = _open_the_template_editor(dialog)

    panel.editor.input_field.clear()
    QTest.keyClicks(panel.editor.input_field, "clips/%(title)s.%(ext)s")
    QApplication.processEvents()

    preview = panel.editor.preview_text()
    # Compared as path components, not as a string: the template is written with `/`, but the
    # preview is a native path, so `endswith("clips/...")` held on Linux and failed on Windows
    # against the same correct `clips\...`. One assertion covers the subfolder and the name.
    assert Path(preview).parts[-2:] == ("clips", "A video with formats.ext"), preview


def test_an_invalid_template_is_refused_at_edit_time_and_never_reaches_the_request(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
    sink: FakeSink,
) -> None:
    """**`T-112`'s criterion, both halves of it.**

    *An invalid template never reaches a download, and the refusal is shown at edit time, with the
    reason* (`P-23`). The second half is where most of the risk is: a dialog that showed the error
    and wrote the template anyway would satisfy the visible half and queue a broken download the
    moment the default button was pressed.
    """
    dialog, row = _staged(dialogs, managers, spin)
    panel = _open_the_template_editor(dialog)
    good = dialog.preset_for(row).output_template

    panel.editor.input_field.clear()
    QTest.keyClicks(panel.editor.input_field, "%(title)")
    QApplication.processEvents()

    assert panel.editor.preview_text() == "", "a refused template still showed a path"
    message = panel.editor.message_text()
    assert "incomplete format" in message, message
    assert dialog.preset_for(row).output_template == good, (
        "the refused template was written to the row, so Add would queue it"
    )

    dialog.close_panel(keep=True)
    dialog.add_to_queue()
    assert spin(lambda: bool(sink.submissions))
    assert sink.submissions[0][0].request.output_template == good


def test_a_template_that_leaves_the_download_folder_is_refused(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
) -> None:
    """Phase 3's fourth exit criterion, reached through the control a user actually types into.

    `tests/unit/test_paths.py` proves `contained_output_path` refuses these; this proves the editor
    is wired to it, which is a different claim and the one a user experiences.
    """
    dialog, row = _staged(dialogs, managers, spin)
    panel = _open_the_template_editor(dialog)
    good = dialog.preset_for(row).output_template

    # `/etc` rather than `/tmp`: the point is an absolute path leaving the download folder, and a
    # `/tmp` literal reads to the linter as a test writing there — which is the one thing this
    # asserts cannot happen.
    for escape in ("../outside/%(title)s.%(ext)s", "/etc/outside/%(title)s.%(ext)s"):
        panel.editor.input_field.setText("")
        QTest.keyClicks(panel.editor.input_field, escape)
        QApplication.processEvents()

        assert panel.editor.preview_text() == "", f"{escape!r} previewed a path"
        assert "outside the chosen directory" in panel.editor.message_text(), (
            panel.editor.message_text()
        )
        assert dialog.preset_for(row).output_template == good, f"{escape!r} reached the row"


def test_an_accepted_template_becomes_the_rows_own_request(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
    sink: FakeSink,
) -> None:
    """Asserted on the submitted `DownloadRequest`, not on the row: the request is what runs."""
    dialog, _row = _staged(dialogs, managers, spin)
    panel = _open_the_template_editor(dialog)

    panel.editor.input_field.clear()
    QTest.keyClicks(panel.editor.input_field, "%(uploader)s/%(title)s.%(ext)s")
    QApplication.processEvents()
    dialog.close_panel(keep=True)

    dialog.add_to_queue()
    assert spin(lambda: bool(sink.submissions))

    assert sink.submissions[0][0].request.output_template == "%(uploader)s/%(title)s.%(ext)s"


def test_escape_puts_the_earlier_template_back(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
) -> None:
    """`Esc` *closes, choosing nothing*, which for this panel means the template it opened with.

    **Both directions**, because a panel that never writes at all would pass the `Esc` half on its
    own. `Done` on the same edit has to land it, or *"choosing nothing"* is the only thing the
    panel can do.
    """
    dialog, row = _staged(dialogs, managers, spin)
    panel = _open_the_template_editor(dialog)
    before = dialog.preset_for(row).output_template
    edited = "elsewhere/%(title)s.%(ext)s"

    panel.editor.input_field.clear()
    QTest.keyClicks(panel.editor.input_field, edited)
    QApplication.processEvents()

    QTest.keyClick(panel, Qt.Key.Key_Escape)
    QApplication.processEvents()

    assert dialog.open_panel is None, "Esc left the panel open"
    assert dialog.preset_for(row).output_template == before

    reopened = _open_the_template_editor(dialog)
    reopened.editor.input_field.clear()
    QTest.keyClicks(reopened.editor.input_field, edited)
    QApplication.processEvents()
    button(dialog, "formatPanelDone").click()
    QApplication.processEvents()

    assert dialog.preset_for(row).output_template == edited, (
        "Done discarded the edit too, so the panel can only ever choose nothing"
    )


def test_an_mp3_row_previews_its_real_extension_and_a_video_row_says_it_cannot(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
) -> None:
    """`REQ-011` as amended: exact where the request decides the container, *intended* where not.

    The two cases in one test because the distinction is the claim — a preview that said
    *provisional* about everything would pass a test of either half on its own.
    """
    dialog, row = _staged(dialogs, managers, spin)

    row.preset = preset_registry.AUDIO_MP3
    exact = dialog.preview_for(row, "%(title)s.%(ext)s")
    assert exact.path.endswith(".mp3"), exact.path
    assert exact.provisional is None, "an MP3 conversion was presented as uncertain"

    row.preset = preset_registry.BEST_VIDEO
    intended = dialog.preview_for(row, "%(title)s.%(ext)s")
    assert intended.provisional is not None, (
        "a merge was presented as an exact path; yt-dlp picks that container itself"
    )
    assert intended.path.endswith(".ext"), intended.path


def test_a_windows_illegal_title_is_previewed_as_the_name_it_will_actually_get(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
) -> None:
    """Phase 3's exit criterion names this case, and it is where a second renderer would show.

    yt-dlp replaces `:` `?` `"` with fullwidth characters of its own on the way out, and
    `core/paths.py` would replace them with `_`. Both preview and write run the same two steps in
    the same order, so the preview shows what yt-dlp did — and a hand-written substituter in `ui/`
    would have shown the underscores instead.
    """
    dialog = dialogs(managers())
    type_urls(dialog, "https://example.invalid/one")
    dialog.resolve()
    assert spin(lambda: bool(dialog.rows and dialog.rows[0].job_id))
    row = dialog.rows[0]
    assert row.job_id is not None
    dialog._on_media_probed(row.job_id, MediaInfo(url=row.url, title='A: Song? "Live" <x>|y*'))
    QApplication.processEvents()

    preview = dialog.preview_for(row, "%(title)s.%(ext)s")

    name = Path(preview.path).name
    assert not set(name) & set('<>:"/\\|?*'), f"an illegal character survived into {name!r}"
    assert "Song" in name and "Live" in name, f"the title was lost rather than cleaned: {name!r}"


def test_the_editor_is_not_offered_on_a_row_that_cannot_be_committed(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
) -> None:
    """`UX-005` §5: nothing is offered that would be refused.

    A row still probing has no request to change and no editor at all — the whole control is
    absent, which is what `PRESET_CHOICES_ROLE` answering `None` means.
    """
    dialog = dialogs(managers(entry_point=child_never_returning))
    type_urls(dialog, "https://example.invalid/slow")
    dialog.resolve()
    assert spin(lambda: bool(dialog.rows and dialog.rows[0].job_id))

    assert role_values(dialog, TEMPLATE_AVAILABLE_ROLE) == [False]
    assert not dialog.edit_row(0), "an unresolved row offered a control"


def test_a_template_too_long_for_the_default_windows_configuration_is_refused(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
) -> None:
    """`T-067`'s finding: **the default configuration is the case to test.**

    `LongPathsEnabled` is `0` on a default Windows and `1` on GitHub's runners, so a path budget
    gated only on CI is gated only under a setting most users do not have. `MAX_PATH_CHARACTERS`
    is enforced in `core/paths.py` before anything touches the filesystem, which is what makes the
    behaviour identical on both platforms and assertable here.

    What `T-112` adds is *when* the user finds out. The refusal arrives at edit time with the
    reason (`P-23`), rather than as a failed download after the bytes have been paid for.
    """
    dialog, row = _staged(dialogs, managers, spin)
    good = dialog.preset_for(row).output_template

    preview = dialog.preview_for(row, f"{'d' * 300}/%(title)s.%(ext)s")

    assert preview.is_refused, f"a path past the budget previewed as {preview.path!r}"
    assert preview.refusal is not None and "no room for a filename" in preview.refusal, (
        preview.refusal
    )
    assert dialog.preset_for(row).output_template == good


def test_a_very_long_title_is_previewed_under_the_name_it_will_be_shortened_to(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
) -> None:
    """The other half of the budget: a title too long is **shortened**, not refused.

    `T-045`'s digest keeps two long titles apart, and the preview has to show the shortened name —
    otherwise the user is shown one filename and gets another, which is the whole of `T-046`'s
    finding one field over. Asserted against `contained_output_path` directly, so what is compared
    is the preview and the function the download names its file with.
    """
    dialog = dialogs(managers())
    type_urls(dialog, "https://example.invalid/one")
    dialog.resolve()
    assert spin(lambda: bool(dialog.rows and dialog.rows[0].job_id))
    row = dialog.rows[0]
    assert row.job_id is not None
    dialog._on_media_probed(row.job_id, MediaInfo(url=row.url, title="t" * 400))
    QApplication.processEvents()

    preview = dialog.preview_for(row, "%(title)s.%(ext)s")

    name = Path(preview.path).name
    assert not preview.is_refused, preview.refusal
    assert len(name.encode("utf-8")) <= MAX_COMPONENT_BYTES, (
        f"{len(name.encode('utf-8'))} bytes previewed, over the {MAX_COMPONENT_BYTES}-byte budget"
    )
    assert name == contained_output_path(dialog._output_directory, "t" * 400 + ".ext").name, (
        "the preview shortened the name differently from the function the download uses"
    )


# --- T-114: a URL the queue already holds is confirmed, not refused (REQ-022, UX_SPEC §9.3) ----
#
# The marking rules are `tests/unit/test_staging.py`. What is here is the dialog: that the row
# says it, that Add still adds it, that a URL matching nothing says nothing at all — and that this
# whole feature writes nothing, which is the design the previous version of the task would have
# drifted back toward.


def _with_queue(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    *,
    holding: Sequence[str],
    pasted: Sequence[str],
) -> AddUrlDialog:
    """A dialog over a queue that already holds `holding`, with `pasted` entered and resolved."""
    dialog = dialogs(managers(entry_point=child_replaying_a_fixture), queued_urls=lambda: holding)
    type_urls(dialog, "\n".join(pasted))
    dialog.resolve()
    assert spin(lambda: bool(dialog.rows) and all(state in SETTLED for state in states(dialog)))
    return dialog


def test_a_url_already_in_the_queue_is_said_on_the_rows_own_state(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`P-26`, ruled 2026-08-07: **a staging-row state**, never a modal.

    A modal per duplicate in a paste of thirty is unusable, and the row is where every other fact
    about a staged line already lives. Asserted through `STATE_ROLE` — the row's *state*, which is
    what the ruling names — rather than anywhere it merely happens to be visible.
    """
    single, playlist = fixture_url(SINGLE_ITEM), fixture_url(PLAYLIST)
    dialog = _with_queue(dialogs, managers, spin, holding=[playlist], pasted=[single, playlist])

    said = role_values(dialog, STATE_ROLE)
    assert "Already in the queue" not in said[0], said[0]
    assert "Already in the queue" in said[1], said[1]
    assert dialog.findChild(QMessageBox) is None, (
        "a modal was raised for a duplicate, which is what UX-007 ruled against"
    )


def test_a_url_repeated_within_one_paste_marks_the_second_occurrence(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`T-114`'s criterion, in the dialog: *the second occurrence, not the first*."""
    single = fixture_url(SINGLE_ITEM)
    dialog = _with_queue(dialogs, managers, spin, holding=[], pasted=[single, single])

    said = role_values(dialog, STATE_ROLE)
    assert "Also pasted above" not in said[0], f"the first line was called a repeat: {said[0]!r}"
    assert "Also pasted above" in said[1], said[1]


def test_a_url_matching_nothing_says_nothing_at_all(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """The silent case, **which an over-eager implementation breaks** — the entry says so.

    A check that marked everything would pass both tests above and make the feature noise.
    """
    single, playlist = fixture_url(SINGLE_ITEM), fixture_url(PLAYLIST)
    dialog = _with_queue(dialogs, managers, spin, holding=[playlist], pasted=[single])

    said = role_values(dialog, STATE_ROLE)[0]
    assert "Already" not in said and "pasted" not in said, said
    assert said == STATE_TEXT[RowState.READY], (
        f"a row repeating nothing says {said!r} rather than its plain state"
    )


def test_confirming_enqueues_the_duplicate_rather_than_skipping_it(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    sink: FakeSink,
    store: FakeStore,
) -> None:
    """**`REQ-022`'s subject**: a duplicate is *confirmed*, not refused (`P-27`).

    Ordinary *Add to queue* is the override and the count includes the duplicates. Asserted on the
    stored queue, because a marking that quietly dropped the row would satisfy every test above.
    """
    single = fixture_url(SINGLE_ITEM)
    dialog = _with_queue(dialogs, managers, spin, holding=[single], pasted=[single, single])

    dialog.add_to_queue()
    assert spin(lambda: bool(sink.submissions))

    submitted = sink.submissions[0]
    assert [job.url for job in submitted] == [single, single], (
        "a duplicate was skipped; REQ-022 says it is confirmed, and both lines were asked for"
    )
    assert len(store.jobs) == 2


def test_the_count_the_dialog_reports_includes_the_duplicates(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    sink: FakeSink,
) -> None:
    """`P-27`: *the count includes the duplicates*, because they are being added."""
    single = fixture_url(SINGLE_ITEM)
    dialog = _with_queue(dialogs, managers, spin, holding=[single], pasted=[single])
    sink.defer = True

    dialog.add_to_queue()

    assert "Adding 1 to the queue" in dialog.status_text(), dialog.status_text()
    sink.release()


def test_a_duplicate_is_spoken_and_not_only_drawn(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`NFR-005`: a state carried by a chip alone is a warning only sighted users receive.

    It joins the row's accessible text, which is where the row's other facts already are, and it
    needs no keyboard route of its own — a row state is not a control.
    """
    single = fixture_url(SINGLE_ITEM)
    dialog = _with_queue(dialogs, managers, spin, holding=[single], pasted=[single])

    spoken = role_values(dialog, Qt.ItemDataRole.AccessibleTextRole)[0]
    assert "Already in the queue" in spoken, spoken


def test_a_job_leaving_the_queue_stops_the_row_calling_itself_a_duplicate(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """The queue moves underneath an open dialog, and the marking has to move with it.

    This is why the dialog holds a **callable** rather than a snapshot: a job finishing or being
    removed while the dialog is open must stop the row claiming a fact that has stopped being true.
    """
    single = fixture_url(SINGLE_ITEM)
    holding = [single]
    dialog = dialogs(managers(entry_point=child_replaying_a_fixture), queued_urls=lambda: holding)
    type_urls(dialog, single)
    dialog.resolve()
    assert spin(lambda: bool(dialog.rows) and all(state in SETTLED for state in states(dialog)))
    assert "Already in the queue" in role_values(dialog, STATE_ROLE)[0]

    holding.clear()
    dialog.refresh()

    assert "Already in the queue" not in role_values(dialog, STATE_ROLE)[0], (
        "the row went on reporting a job the queue no longer holds"
    )


def test_the_duplicate_check_writes_nothing(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
    store: FakeStore,
) -> None:
    """**`T-114`'s last criterion**, and the one the previous design of this task would break.

    It used to depend on a durable record of completed downloads; `REQ-020` is withdrawn and
    migration `0009` dropped the table. So the check must add no row, no table and no column —
    asserted as *no write of any kind reached the store* while a paste with duplicates in it was
    staged and marked.
    """
    single = fixture_url(SINGLE_ITEM)
    _with_queue(dialogs, managers, spin, holding=[single], pasted=[single, single])

    assert store.jobs == {}, "staging a duplicate wrote a row"
    assert store.writes == [], f"staging a duplicate wrote something: {store.writes}"


def test_the_check_asks_the_queue_in_memory_rather_than_querying_it(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`T079-R2`: no query is added to the GUI thread's path.

    The scan runs on every refresh — which is every keystroke, through the debounce — so what is
    asserted is that the dialog asks a **callable it was handed** rather than reading a database.
    That the answer comes from rows already in memory is `QueueModel.queued_urls`'s claim.
    """
    asked = 0

    def queued() -> tuple[str, ...]:
        nonlocal asked
        asked += 1
        return ()

    dialog = dialogs(managers(entry_point=child_replaying_a_fixture), queued_urls=queued)
    type_urls(dialog, fixture_url(SINGLE_ITEM))
    dialog.resolve()
    assert spin(lambda: bool(dialog.rows) and all(state in SETTLED for state in states(dialog)))

    assert asked > 0, "the dialog never asked what the queue holds, so nothing can be a duplicate"


def test_a_dialog_told_nothing_about_the_queue_reports_no_duplicates(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """The default is *no duplicates*, not a guess about where a queue lives.

    A caller that never said what the queue contains gets the honest answer, and this dialog does
    not learn what a queue view is in order to find out.
    """
    single = fixture_url(SINGLE_ITEM)
    dialog = dialogs(managers(entry_point=child_replaying_a_fixture))
    type_urls(dialog, single)
    dialog.resolve()
    assert spin(lambda: bool(dialog.rows) and all(state in SETTLED for state in states(dialog)))

    assert role_values(dialog, STATE_ROLE)[0] == STATE_TEXT[RowState.READY]


# --- REQ-007 / P-7: a new paste inherits the default preset (T-111) -------------------------


def test_the_batch_opens_on_the_default_preset(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
) -> None:
    """*The default preset is what a new paste inherits* — the point of there always being one.

    Asserted on `selected_preset`, which is what `preset_for` hands every row that has not
    overridden it, rather than on the combo's index: the index is how it is drawn, and what the
    download uses is the question `REQ-009` cares about.
    """
    catalogue = preset_registry.BUILT_IN_PRESETS
    dialog = dialogs(managers(), presets=catalogue, default_preset=catalogue[2].name)

    assert dialog.selected_preset.name == catalogue[2].name


def test_no_default_leaves_the_batch_on_the_first_entry(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
) -> None:
    """What the control did before there was a default, kept for callers that name none."""
    catalogue = preset_registry.BUILT_IN_PRESETS
    dialog = dialogs(managers(), presets=catalogue)

    assert dialog.selected_preset.name == catalogue[0].name


def test_a_default_naming_nothing_in_the_catalogue_falls_back(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
) -> None:
    """Not reachable through `default_preset_of`, which only answers with a preset that exists.

    This dialog is constructible directly, so falling back is cheaper than requiring every caller
    to have resolved the name first — and a control on *nothing* would be the real failure.
    """
    catalogue = preset_registry.BUILT_IN_PRESETS
    dialog = dialogs(managers(), presets=catalogue, default_preset="Never existed")

    assert dialog.selected_preset.name == catalogue[0].name


# --- T-111: the Manage presets… entry on the format control (UX_SPEC §8's P-6) --------------


def test_an_open_playlist_shows_entries_and_a_way_back(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """**`T-210`.** *"The table is still way too small to actually scroll and read"*, and *"you also
    still cannot re-collapse it back to a playlist view."*

    Two causes, one measurement each.

    **The summary was the whole row.** `RowPanel` reproduced `row_text`, which ends with the format
    selector — `bestvideo[height<=1080][ext=mp4]+bestaudio[...]` — wrapping to two more lines inside
    a panel bounded by the viewport. The entries got what was left, which was one of sixteen. It now
    shows `row_summary`: the same composed pieces, without the tail the control beside it already
    answers.

    **The way out was at the bottom.** `setIndexWidget` covers the row's own disclosure while the
    panel is open, so the panel supplies the control that closes it — and `Done`, at the bottom, is
    the first thing below the fold on a tall panel. A collapse triangle now sits at the top, where
    it cannot be pushed off.
    """
    dialog, row = _staged_playlist(dialogs, managers, spin)
    dialog.resize(900, 700)
    dialog.show()
    QApplication.processEvents()

    panel = _open_the_picker(dialog, row)
    QApplication.processEvents()
    viewport = staging_list(dialog).viewport()

    try:
        # **A refresh straight after opening**, which is what the dialog actually does. The first
        # `T204-R4` fix restored geometry *inside* the `dataChanged` emit, before Qt re-measured
        # the view, so `visualRect` answered a stale — sometimes empty — rectangle and the panel
        # was erased the instant it opened. The committed tests processed events and missed it.
        opened_at = panel.geometry()
        dialog.refresh()
        QApplication.processEvents()
        assert panel.geometry() == opened_at, (
            f"a refresh moved the panel from {opened_at} to {panel.geometry()}"
        )
        assert panel.isVisible() and panel.height() > 0, "the panel vanished when it was refreshed"
        assert panel.property("rowPanel") is True, (
            "the panel is not styled by the rowPanel role, so the sheet paints no background for "
            "it — and the delegate's row, thumbnail and all, shows through underneath"
        )
        assert panel.autoFillBackground(), "the unstyled fallback fill is gone too"

        # **One arrow, not two** (`T-210`). The panel supplies the way out; the delegate must stop
        # painting the open state or every expanded row carries a pair of them.
        model = dialog._model
        opened = model.index(dialog.rows.index(row), 0)
        assert model.data(opened, EXPANDED_ROLE) is True, "the row is not recorded as open"

        # **Resizing the window must not break it** (`T-210`). An opened row's height is bounded by
        # the viewport now, and Qt does not re-ask a delegate for `sizeHint` when the viewport
        # changes — so without a resize hook the row kept a height measured against the old
        # viewport while the panel was laid out to the new one, and the row showed nothing at all.
        dialog.resize(900, 900)
        QApplication.processEvents()
        assert panel.isVisible() and panel.height() > 0, "growing the window emptied the panel"
        grown = dialog._model.index(dialog.rows.index(row), 0)
        assert staging_list(dialog).visualRect(grown).height() == panel.height(), (
            "after a resize the row and its panel disagree about how tall the row is"
        )

        table = panel.picker.table
        row_height = table.rowHeight(0)
        assert row_height > 0
        visible_rows = table.viewport().height() // row_height
        assert visible_rows >= 4, (
            f"the picker shows {visible_rows} of 7 entries in a {viewport.height()}px viewport; "
            "the panel is spending its height on something other than the entries"
        )

        collapse = panel.collapse_button
        assert collapse.property("disclosure") is True, (
            "the collapse control is not styled by the disclosure role, so it draws as a framed "
            "button beside a painted triangle — two looks for one gesture"
        )
        bottom = collapse.mapTo(viewport, collapse.rect().bottomLeft()).y()
        assert 0 <= bottom <= viewport.height(), (
            f"the collapse control is at y={bottom} in a {viewport.height()}px viewport, so the "
            "pointer has no visible way back to the closed row"
        )

        collapse.click()
        QApplication.processEvents()
        assert dialog.open_panel is None, "the collapse control did not close the panel"
    finally:
        dialog.close()


def test_the_panel_fits_the_viewport_at_the_size_the_criteria_claim(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """**`T210-R1`, and the bound is asserted where it is claimed rather than well inside it.**

    The committed regression opened at 700px and grew to 900px, so it never touched the size the
    task admitted was a problem. Codex measured the gap: 600px window → 213px viewport, 210px
    panel; 550px → 163px; 500px → 113px. The panel keeps its `minimumSizeHint` at all three, so
    below roughly 600px it is taller than the viewport and *Done* is under the fold.

    **The maintainer ruled the small window out of scope on 2026-08-09** — *"go with your
    suggestion for T210-R1"*, against the recommendation that fitting a 113px viewport costs the
    picker every visible entry, which is the *"you can barely see a playlist"* complaint T-210
    exists to answer. So this test states the real contract in two halves: **the criteria hold at
    600px**, and **below it the documented route out is the one that must keep working.**

    This is a bound, not a success. The gap is real and named; what is asserted is that it behaves
    the way the task now says it does.
    """
    dialog, row = _staged_playlist(dialogs, managers, spin)
    dialog.resize(900, 600)
    dialog.show()
    QApplication.processEvents()

    panel = _open_the_picker(dialog, row)
    QApplication.processEvents()

    try:
        viewport = staging_list(dialog).viewport()
        assert panel.height() <= viewport.height(), (
            f"at the claimed bound the panel is {panel.height()}px in a {viewport.height()}px "
            "viewport — the criterion is stated for this size and does not hold at it"
        )
        done_bottom = panel.done_button.mapTo(viewport, panel.done_button.rect().bottomLeft()).y()
        assert 0 <= done_bottom <= viewport.height(), (
            f"Done ends at y={done_bottom} in a {viewport.height()}px viewport at the claimed bound"
        )

        # **Below the bound: the panel keeps its minimum and the top control is the way out.**
        # Shrinking further would cost the entries, so the panel deliberately stops giving.
        for height in (550, 500):
            dialog.resize(900, height)
            QApplication.processEvents()
            viewport = staging_list(dialog).viewport()
            assert panel.height() >= panel.minimumSizeHint().height(), (
                f"at {height}px the panel shrank past its minimum, which costs the entries the "
                "picker exists to show"
            )
            collapse = panel.collapse_button
            top = collapse.mapTo(viewport, collapse.rect().topLeft()).y()
            assert 0 <= top <= viewport.height(), (
                f"at {height}px the collapse control is at y={top} in a {viewport.height()}px "
                "viewport — below the bound it is the only pointer route out, so it must stay"
            )

        collapse = panel.collapse_button
        collapse.click()
        QApplication.processEvents()
        assert dialog.open_panel is None, (
            "the documented route out of a panel too tall for the viewport did not close it"
        )
    finally:
        dialog.close()


def test_a_value_refresh_leaves_the_open_panel_over_its_row(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """**`T204-R4`.** A value-only refresh re-measured the row and left the panel behind.

    `StagingModel.refresh` emits `dataChanged` with **no roles**, so it carries `SizeHintRole` and
    the view re-lays the row out. An index widget keeps whatever geometry it was last given, so the
    panel collapsed toward its minimum while the row stayed tall — the picker body and *Done* were
    clipped, and the delegate's painting showed through underneath. That is `T-204`'s criterion 6,
    and it is why the pointer had no way to close the panel.

    **Shown, and asserted on geometry.** The committed regression for `T204-R1` neither showed the
    dialog nor measured the panel, which is exactly why a green suite hid this.
    """
    dialog, row = _staged_playlist(dialogs, managers, spin)
    dialog.resize(900, 700)
    dialog.show()
    QApplication.processEvents()

    panel = _open_the_picker(dialog, row)
    QApplication.processEvents()
    listing = staging_list(dialog)
    before = panel.size()
    assert before.height() > 100, f"the panel never opened to a usable size: {before}"

    try:
        # The reachable transition from `T204-R1`: the row's job leaves the queue.
        job_id = row.job_id
        assert isinstance(job_id, str) and job_id
        dialog._on_job_changed(job_id, JobStatus.CANCELLED.value)
        QApplication.processEvents()

        index = dialog._model.index(dialog.rows.index(row), 0)
        assert panel.size() == before, (
            f"the value refresh shrank the panel from {before} to {panel.size()}"
        )
        assert panel.geometry() == listing.visualRect(index), (
            "the panel no longer covers its row, so the row paints through underneath"
        )

        # And it can still be closed by the control the panel offers.
        panel.done_button.click()
        QApplication.processEvents()
        assert dialog.open_panel is None, "the panel's own Done button did not close it"
    finally:
        dialog.close()


def test_the_reachable_failed_path_keeps_the_panel_and_the_selection(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    qapp: QApplication,
    spin: Callable[..., bool],
) -> None:
    """**`T-209`, run as specified**: the real signal, a real keystroke, and the user's route out.

    The neighbouring `T204-R4` test drives the slot directly and never touches the selection.
    This one is the criterion verbatim: the selection is changed with `Space` **first**, the
    failure arrives through `manager.job_changed` — the connection a user's session actually
    exercises — and after the value refresh the panel must still be the row's index widget,
    still cover the row, and still hand back the half-made choice through its own *Done*.
    """
    dialog, row = _staged_playlist(dialogs, managers, spin)
    dialog.resize(900, 700)
    dialog.show()
    qapp.processEvents()
    _open_the_picker(dialog, row)
    qapp.processEvents()
    # Through the typed property rather than the helper's `Any`, so the index-widget identity
    # assert below narrows to `PlaylistPanel` and not to bare `QWidget`.
    panel = dialog.open_playlist_panel
    assert panel is not None
    listing = staging_list(dialog)

    try:
        QTest.keyClick(panel.picker.table, Qt.Key.Key_Space)
        qapp.processEvents()
        chosen = row.entry_selection
        assert isinstance(chosen, PlaylistSelection) and len(chosen.checked) == 6

        job_id = row.job_id
        assert isinstance(job_id, str) and job_id
        dialog._manager.job_changed.emit(job_id, JobStatus.CANCELLED.value)
        qapp.processEvents()
        assert row.state is RowState.FAILED, "the reachable path did not reach FAILED"

        index = dialog._model.index(dialog.rows.index(row), 0)
        assert listing.indexWidget(index) is panel, (
            "after the value refresh the panel is no longer the row's index widget"
        )
        assert panel.geometry() == listing.visualRect(index), (
            f"the panel sits at {panel.geometry()} while its row is at "
            f"{listing.visualRect(index)} — the delegate's row paints through the difference"
        )
        viewport = listing.viewport()
        done_bottom = panel.done_button.mapTo(viewport, panel.done_button.rect().bottomLeft()).y()
        assert 0 <= done_bottom <= viewport.height(), "Done left the viewport with the refresh"

        panel.done_button.click()
        qapp.processEvents()
        assert dialog.open_panel is None, "Done did not close the panel"
        assert row.entry_selection == chosen, (
            f"the failure refresh cost the user their half-made choice: "
            f"{row.entry_selection} != {chosen}"
        )
    finally:
        dialog.close()


def test_a_value_refresh_leaves_the_open_format_table_over_its_row(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    qapp: QApplication,
    spin: Callable[..., bool],
) -> None:
    """**`T-209`'s audit, the other panel kind.** The correction is `relayout_panel`, which moves
    whatever panel is open — but "it should generalise" is exactly the claim the audit exists to
    replace with a measurement, because the geometry seam has needed two corrections already.

    Same reachable path as the playlist case, on the **format table**: the row's job leaves the
    queue, the value refresh re-measures the row, and the table must still cover it. Closed with
    `Esc`, the format table's own discard route.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM, AUDIO_ONLY)
    dialog.resize(900, 700)
    dialog.show()
    qapp.processEvents()
    row = dialog.rows[0]
    dialog.open_format_table(row)
    # Two turns, deliberately: `_open_panel` defers the mount (`T108-R2`'s ordering) and the
    # geometry lands on the turn after the widget does — the audit's finding about *every* open,
    # recorded in the entry as the one-turn transient.
    qapp.processEvents()
    qapp.processEvents()
    panel = dialog.open_format_panel
    assert panel is not None, "the row did not open into its format table"
    listing = staging_list(dialog)
    before = panel.size()
    assert before.height() > 100, f"the table never opened to a usable size: {before}"

    try:
        job_id = row.job_id
        assert isinstance(job_id, str) and job_id
        dialog._manager.job_changed.emit(job_id, JobStatus.CANCELLED.value)
        qapp.processEvents()
        assert row.state is RowState.FAILED

        index = dialog._model.index(dialog.rows.index(row), 0)
        assert panel.size() == before, (
            f"the value refresh shrank the format table from {before} to {panel.size()}"
        )
        assert panel.geometry() == listing.visualRect(index), (
            "the format table no longer covers its row"
        )

        QTest.keyClick(panel, Qt.Key.Key_Escape)
        qapp.processEvents()
        assert dialog.open_panel is None, "Esc did not close the format table"
    finally:
        dialog.close()


def _wheel_down(target: QWidget) -> QWheelEvent:
    """One notch of wheel-down, aimed at `target`'s centre."""
    centre = QPointF(target.rect().center())
    return QWheelEvent(
        centre,
        QPointF(target.mapToGlobal(target.rect().center())),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def test_the_footer_offers_the_preset_manager_where_a_store_is_wired(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
) -> None:
    """`UX-009`: a library-wide action does not belong on a row.

    *Manage presets…* edits the catalogue **every** row chooses from and does the same thing from
    every one of them, so being an entry in each row's format control offered it N times to mean
    once. It is now a button in the dialog's footer.

    *(`UX_SPEC` §8's `[T]` clause read "reached from the format control's `Manage presets…`" until
    `UX-009` amended it on 2026-08-09.)*
    """
    dialog, _row = _staged(dialogs, managers, spin, manage_presets=lambda: None)

    button = dialog.findChild(QPushButton, "managePresetsButton")
    assert button is not None, "the footer does not offer the preset manager at all"
    assert button.isEnabled(), "a wired manager left the button dead"
    assert button.accessibleName() == "Manage presets", (
        "the button has no accessible name, which `NFR-005` requires of every control"
    )

    control = open_row_editor(dialog, 0)
    entries = [control.itemText(index) for index in range(control.count())]
    assert MANAGE_PRESETS_TEXT not in entries, (
        f"the row's control still offers the library-wide action: {entries}"
    )


def test_the_footer_button_is_dead_rather_than_missing_where_nothing_is_wired(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
) -> None:
    """Disabled, not hidden — `focus_chain`'s own rule for this row of buttons.

    The combo entry this replaces was **omitted** when nothing was wired, which is `UX-005` §5. The
    button row answers the same question differently and says so: *"nothing here hides: the retry
    button is disabled rather than removed … so the chain is the same in every state."* Hiding it
    would make the declared keyboard order depend on what composition wired, which is what `T-060`
    and `T016-R4` exist to prevent.
    """
    dialog, _row = _staged(dialogs, managers, spin)

    button = dialog.findChild(QPushButton, "managePresetsButton")
    assert button is not None, "the button was removed rather than disabled"
    assert not button.isEnabled(), "nothing is wired behind it and it still invites a click"
    assert button in dialog.focus_chain(), (
        "a disabled-but-present button left the declared keyboard order, so the order now depends "
        "on composition's wiring"
    )


def test_the_entry_is_absent_where_nothing_is_wired_behind_it(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
) -> None:
    """`UX-005` §5: nothing is drawn that would be refused.

    A dialog composed without a preset store has nowhere for the manager to save, so the entry is
    not offered at all — the same rule `OptionsDialog` applies to *Save as preset…*.
    """
    dialog, _row = _staged(dialogs, managers, spin)
    control = open_row_editor(dialog, 0)
    entries = [control.itemText(index) for index in range(control.count())]

    assert MANAGE_PRESETS_TEXT not in entries, entries


def test_choosing_the_entry_opens_the_manager_and_keeps_the_row_s_format(
    qapp: QApplication,
    managers: Callable[..., DownloadManager],
    dialogs: Callable[..., AddUrlDialog],
    spin: Callable[..., bool],
) -> None:
    """The sentinel must reach `open_preset_manager` and **not** the preset lookup.

    `setData` looks any string up as a preset name and writes the answer onto the row, so a
    sentinel that fell through would find nothing and silently clear the format the user chose.
    Asserted on the row as well as the call, because the call being made does not by itself mean
    the lookup was skipped — which is the defect the three sibling sentinels each guard against.
    """
    opened: list[bool] = []
    dialog, row = _staged(dialogs, managers, spin, manage_presets=lambda: opened.append(True))
    row.preset = preset_registry.AUDIO_MP3

    index = dialog.model.index(0, 0)
    assert dialog.model.setData(index, MANAGE_PRESETS_DATA, PRESET_ROLE)

    assert opened == [], (
        "the manager opened inside setData, i.e. underneath Qt's commitData stack (T111-R3)"
    )
    QApplication.processEvents()

    assert opened == [True]
    assert row.preset is preset_registry.AUDIO_MP3, (
        "the sentinel reached the preset lookup and cleared the row's chosen format"
    )


def test_teardown_forgets_the_editor_whatever_row_it_is_billed_to(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """**`T-211`.** The crash from the maintainer's konsole, reproduced at its seam.

    `destroyEditor` compared the index's row to the remembered one — but Qt destroys editors
    *during* a reset, after rows have shifted, so the row it names at teardown is `T118-R14`'s
    untrustworthy number exactly. On a mismatch the delegate kept `_editor` pointing at a deleted
    widget; the next `commit_open_editor` then walked into it — two *"editor that does not belong
    to this view"* warnings, then `RuntimeError: Internal C++ object already deleted`.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM, PLAYLIST)
    listing = staging_list(dialog)
    delegate = listing.itemDelegate()
    assert isinstance(delegate, RowDelegate)

    control = open_row_editor(dialog, 0)
    # Read into locals: mypy narrows the *property* across asserts, so `is not None` here followed
    # by `is None` below reads as a contradiction and everything after it as unreachable — the
    # `P3EXIT-R2` family, one gate over.
    opened = delegate.editing_job_id
    assert opened is not None

    # Qt bills the destruction to whatever the index resolves to *now* — a shifted row.
    delegate.destroyEditor(control, dialog._model.index(1, 0))
    QApplication.processEvents()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    remembered = delegate.editing_job_id
    assert remembered is None, (
        "teardown trusted the row number and kept a reference to a deleted editor"
    )
    # The crash site: with the stale reference cleared this is a no-op, not a RuntimeError.
    assert dialog.commit_open_editor() is False


def test_the_row_control_offers_only_presets(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """**`T-203`, the point of it.** Every entry in the combo is a value that sticks.

    The verbs opened windows and put the selection back — a value picker containing commands. They
    are the row's menu's now (`UX-011`, option *E*), so the honest assertion is exhaustive: nothing
    in this control carries sentinel data, and none of the verb wordings appears.
    """
    dialog, _row = _staged(dialogs, managers, spin)
    control = open_row_editor(dialog, 0)
    entries = [control.itemText(i) for i in range(control.count())]
    data = [control.itemData(i) for i in range(control.count())]

    for verb in (CHOOSE_FORMATS_TEXT, OPTIONS_TEXT, TEMPLATE_TEXT, MANAGE_PRESETS_TEXT):
        assert verb not in entries, f"{verb!r} is still an entry: {entries}"
    for value in data:
        assert value is None or not str(value).startswith("\x00"), (
            f"a sentinel survived in the combo: {data}"
        )


def test_the_menu_offers_what_the_row_can_do(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """The row's menu offers what that row can actually do, by absence (`T-203`, `UX-011`).

    A single item offers the format table; a playlist does not — its formats belong to its
    entries (`T-110`) — and under option *E* the menu says so the way it already said Retry:
    the entry is **not there**, following the menu's own idiom for conditional entries rather
    than the bar's enablement.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM, PLAYLIST)

    single = dialog.row_menu(dialog.rows[0])
    texts = [action.text() for action in single.actions() if not action.isSeparator()]
    assert texts[:3] == [CHOOSE_FORMATS_TEXT, OPTIONS_TEXT, TEMPLATE_TEXT], (
        f"a ready single item's verbs are {texts}, not the three under Just this item"
    )
    assert "Remove this URL" in texts
    assert "Read this URL again" not in texts, "Retry is offered on a row that has not failed"
    # **The heading is real menu furniture, not a comment**: a separator action carrying the
    # `UX-011` wording, above the verbs it introduces.
    sections = [action.text() for action in single.actions() if action.isSeparator()]
    assert "Just this item" in sections

    playlist = dialog.row_menu(dialog.rows[1])
    playlist_texts = [action.text() for action in playlist.actions()]
    assert CHOOSE_FORMATS_TEXT not in playlist_texts, (
        "a playlist offers the format table, but its formats belong to its entries"
    )
    assert OPTIONS_TEXT in playlist_texts and TEMPLATE_TEXT in playlist_texts, (
        "the per-item verbs a playlist genuinely has went missing with the one it does not"
    )


def test_the_menu_acts_on_the_row_it_was_opened_from(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """**`T203-R1`'s successor, and the criterion that proves the shape** (`T-203`, `UX-011`).

    The bar acted on the *current* row and had to announce which one that was — the announcement
    was the machinery `T203-R1` found missing. A menu is opened *from* a row; opened on row 1
    while row 0 is current, its verbs act on row 1. Nothing announces a target because nothing
    needs to: the target is structural.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM, AUDIO_ONLY)
    listing = staging_list(dialog)
    listing.selectionModel().setCurrentIndex(
        dialog.model.index(0, 0), QItemSelectionModel.SelectionFlag.NoUpdate
    )

    menu = dialog.row_menu(dialog.rows[1])
    wanted = [action for action in menu.actions() if action.text() == CHOOSE_FORMATS_TEXT]
    assert wanted, "row 1 offers no format table"
    wanted[0].trigger()
    QApplication.processEvents()

    assert dialog.expanded_row is dialog.rows[1], (
        "the menu was opened from row 1 and acted on a different row"
    )
    assert listing.currentIndex().row() == 0, (
        "acting on the opened-from row should not have required making it current"
    )


def _popped_menu(listing: QListView) -> QMenu:
    """The row menu a door just opened, and there must be exactly one.

    `_show_row_menu` pops the menu up rather than exec-ing it — a nested event loop cannot be
    returned from headlessly — so the opened menu is a real, visible child the test can read.
    """
    menus = [menu for menu in listing.findChildren(QMenu) if menu.isVisible()]
    assert len(menus) == 1, f"{len(menus)} row menus are open at once"
    return menus[0]


def _close_menu(menu: QMenu) -> None:
    """Close a popped-up menu and let its deferred deletion actually run (`WA_DeleteOnClose`)."""
    menu.close()
    QApplication.processEvents()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_the_two_doors_produce_the_same_actions(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    qapp: QApplication,
    spin: Callable[..., bool],
) -> None:
    """One menu, not two lookalikes (`T-203`, `UX-011`): the `⋮` and the context route agree.

    Asserted **on the actions each door produces**, not on two builders happening to look alike:
    both doors are driven — the context route with a point over the row, the `⋮` zone with a real
    click through the delegate — and the two menus they open must offer the same entries in the
    same order.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM, AUDIO_ONLY)
    listing = staging_list(dialog)
    dialog.show()
    try:
        qapp.processEvents()
        index = listing.model().index(0, 0)

        dialog._show_row_menu(listing.visualRect(index).center())
        by_context = [action.text() for action in _popped_menu(listing).actions()]
        _close_menu(_popped_menu(listing))

        option = QStyleOptionViewItem()
        option.rect = listing.visualRect(index)
        option.font = listing.font()
        option.fontMetrics = QFontMetrics(option.font)
        delegate = listing.itemDelegate()
        assert isinstance(delegate, RowDelegate)
        QTest.mouseClick(
            listing.viewport(),
            Qt.MouseButton.LeftButton,
            pos=delegate._menu_zone_of(option, index).center(),
        )
        qapp.processEvents()
        by_zone = [action.text() for action in _popped_menu(listing).actions()]
        _close_menu(_popped_menu(listing))

        assert by_context == by_zone, (
            f"the two doors disagree: context {by_context} versus ⋮ {by_zone}"
        )
        assert CHOOSE_FORMATS_TEXT in by_context, (
            "neither door offered the format table for a ready single item"
        )
    finally:
        dialog.hide()


def test_the_menu_key_reaches_the_current_rows_menu(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    qapp: QApplication,
    spin: Callable[..., bool],
) -> None:
    """**`T203-R3`'s regression.** The keyboard door opens the *current* row's menu.

    Driven through Qt's own `CustomContextMenu` dispatch on a shown dialog, with the object the
    Menu key produces: a keyboard-reason context event positioned **off every row**, because its
    position derives from the widget rather than from a row (`test_row_verb_wiring.py`'s
    `_press_the_menu_key`, including why the literal key press cannot be sent under `offscreen`).
    A handler that resolves only `indexAt` answers "no row" for every keyboard request — the
    two-door test above calls `_show_row_menu` with a row-centred point, so it proves a second
    pointer-shaped route and could not see this one dead.

    The current row is the **playlist**, whose menu differs from row 0's by absence
    (`T-110`: no format-table entry), so the assertion also proves *which* row the fallback
    resolved: the current one, not whatever happens to sit under the widget-derived point.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM, PLAYLIST)
    listing = staging_list(dialog)
    dialog.show()
    try:
        qapp.processEvents()
        assert listing.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu, (
            "without this policy the platform routes the Menu key to a default menu instead of "
            "to this application, and the row's verbs stay pointer-only"
        )
        current = dialog.model.index(1, 0)
        listing.selectionModel().setCurrentIndex(
            current, QItemSelectionModel.SelectionFlag.NoUpdate
        )

        viewport = listing.viewport()
        last = listing.visualRect(dialog.model.index(dialog.model.rowCount() - 1, 0))
        off_any_row = QPoint(1, max(last.bottom() + 2, viewport.height() + 2))
        assert not listing.indexAt(off_any_row).isValid(), (
            "the probe position landed on a row, so this asserts the mouse route rather than "
            "the keyboard one"
        )
        QApplication.sendEvent(
            viewport,
            QContextMenuEvent(
                QContextMenuEvent.Reason.Keyboard, off_any_row, viewport.mapToGlobal(off_any_row)
            ),
        )
        qapp.processEvents()

        menu = _popped_menu(listing)
        offered = [action.text() for action in menu.actions() if not action.isSeparator()]
        expected = [
            action.text()
            for action in dialog.row_menu(dialog.rows[1]).actions()
            if not action.isSeparator()
        ]
        assert offered == expected, (
            f"the keyboard door offers {offered}, not the current row's menu {expected}"
        )
        assert CHOOSE_FORMATS_TEXT not in offered, (
            "the format table is offered, so this is row 0's menu — the fallback resolved the "
            "wrong row"
        )
        anchor = viewport.mapFromGlobal(menu.pos())
        assert listing.visualRect(current).contains(anchor), (
            f"the menu popped at viewport {anchor}, not anchored on the current row "
            f"{listing.visualRect(current)} — a keyboard opening placed off its row"
        )
        _close_menu(menu)

        # The other half of the fallback's guard: with no current row the keyboard request has
        # no row to answer for, and the door opens nothing rather than guessing.
        listing.selectionModel().setCurrentIndex(
            QModelIndex(), QItemSelectionModel.SelectionFlag.NoUpdate
        )
        QApplication.sendEvent(
            viewport,
            QContextMenuEvent(
                QContextMenuEvent.Reason.Keyboard, off_any_row, viewport.mapToGlobal(off_any_row)
            ),
        )
        qapp.processEvents()
        assert not [child for child in listing.findChildren(QMenu) if child.isVisible()], (
            "with no current row and no row under the point, a menu opened anyway"
        )
    finally:
        dialog.hide()


def test_the_menu_zone_is_carved_from_the_control_and_both_sides_work(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    qapp: QApplication,
    spin: Callable[..., bool],
) -> None:
    """The `⋮` zone's geometry, and both sides of its line (`T-203`).

    This is the delegate's paint-and-hit-test seam — `T107-R2`, `T108-R2`, `T-204` — so the zone
    gets what the twisty got: its rectangle asserted against the control it is carved from, and a
    click driven at real coordinates on **each** side. In the zone: the menu, and no editor.
    On the combo: the editor, exactly as before the zone existed.
    """
    dialog, _ = resolved(dialogs, managers, spin, SINGLE_ITEM, AUDIO_ONLY)
    listing = staging_list(dialog)
    dialog.show()
    try:
        qapp.processEvents()
        index = listing.model().index(0, 0)
        option = QStyleOptionViewItem()
        option.rect = listing.visualRect(index)
        option.font = listing.font()
        option.fontMetrics = QFontMetrics(option.font)
        delegate = listing.itemDelegate()
        assert isinstance(delegate, RowDelegate)

        control = delegate._control_of(option, index)
        zone = delegate._menu_zone_of(option, index)
        assert zone.width() == MENU_ZONE_WIDTH, "the zone is not the fixed width it promises"
        assert zone.right() == control.right() and zone.top() == control.top(), (
            f"the zone {zone} is not flush with the control's trailing edge {control}"
        )
        assert control.contains(zone), "the zone left the control it is carved from"

        QTest.mouseClick(listing.viewport(), Qt.MouseButton.LeftButton, pos=zone.center())
        qapp.processEvents()
        opened = _popped_menu(listing)
        assert not listing.findChildren(QComboBox, ROW_PRESET_NAME), (
            "a click in the ⋮ zone opened the preset combo as well as the menu"
        )
        _close_menu(opened)

        combo_half = QPoint(
            control.left() + (control.width() - MENU_ZONE_WIDTH) // 2, control.center().y()
        )
        QTest.mouseClick(listing.viewport(), Qt.MouseButton.LeftButton, pos=combo_half)
        qapp.processEvents()
        assert len(listing.findChildren(QComboBox, ROW_PRESET_NAME)) == 1, (
            "a click on the combo's own half no longer opens the preset editor"
        )
        assert not [menu for menu in listing.findChildren(QMenu) if menu.isVisible()], (
            "the combo click leaked into the ⋮ zone"
        )
    finally:
        dialog.hide()


def test_the_manager_opens_a_turn_after_the_button_is_pressed(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
    spin: Callable[..., bool],
) -> None:
    """`T111-R3`'s deferral survives the move to the footer, and is kept deliberately.

    **The hazard it was written for is gone.** `open_preset_manager` used to be reached from
    `StagingModel.setData`, which Qt calls inside `commitData` while the row's combo is still
    open — so a modal manager ran a nested event loop underneath a widget Qt was in the middle of
    closing, which is `T108-R2`'s dead-editor class. `UX-009` moved the route to a footer button,
    and a button press is not inside anyone's `commitData`.

    **The deferral stays anyway.** It costs one turn from a click and is the whole of the
    protection if any route ever reaches this method from an editor again. This asserts it is
    still a turn late rather than synchronous.
    """
    opened: list[bool] = []
    dialog, _row = _staged(dialogs, managers, spin, manage_presets=lambda: opened.append(True))

    button = dialog.findChild(QPushButton, "managePresetsButton")
    assert button is not None and button.isEnabled()
    button.click()

    assert opened == [], "the manager opened synchronously; T111-R3's deferral is gone"

    QApplication.processEvents()
    assert opened == [True], "the deferred manager never opened at all"
