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
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, Final

import pytest
from PySide6.QtCore import QEvent, QRect, Qt
from PySide6.QtGui import QColor, QFontMetrics, QImage, QPainter
from PySide6.QtWidgets import (
    QAbstractItemDelegate,
    QApplication,
    QComboBox,
    QLabel,
    QListView,
    QPlainTextEdit,
    QPushButton,
    QStyleOptionViewItem,
    QWidget,
)

from tracks_and_trails.core import presets as preset_registry
from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import (
    DownloadRequest,
    Job,
    MediaInfo,
    MediaKind,
)
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
    describe_kind,
    format_duration,
    row_text,
    split_urls,
)
from tracks_and_trails.ui.row_delegate import (
    EDIT_HINT,
    PADDING,
    ROW_HEIGHT,
    ROW_PRESET_NAME,
)
from tracks_and_trails.ui.staging import SETTLED, RowState

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
#: replaced would spend seconds here, not milliseconds. The *finer* claim — that cost stays linear
#: — is `SCALING_HEADROOM`'s, which is a ratio and so does not move with runner speed at all.
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
#: **A ratio, on purpose.** Two measurements taken moments apart on one machine share its speed, so
#: a slow runner slows both sides and cancels out — which is the term that made `T118-R10`'s gate
#: flap, and the same defect `T083-R2` records elsewhere in this repository.
SCALING_HEADROOM: Final = 6.0

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
    "stagingList",
    # Selectable, therefore focusable, therefore declared (`T016-R4`).
    "statusMessage",
    "presetChoice",
    # `T-076`. Placed with the preset it qualifies rather than at the end: a user who has just
    # chosen "Audio only (MP3)" is one Tab away from the bitrate that preset will convert at.
    "audioBitrateChoice",
    "selectorValue",
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
        self.completions: list[tuple[str, str | None]] = []
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

    def complete(
        self, job: Job, format_used: str | None, done: Callable[[str | None], None]
    ) -> None:
        """`JobStore.complete` — the job row and its history record, atomically (`T050-R1`).

        A fake, so "atomically" is trivial: one dict assignment cannot half-happen. What it
        preserves is the *shape* — one call, one settlement — so the manager cannot be
        written against two separate writes and still pass here.
        """
        self.completions.append((job.id, format_used))
        self.update(job, done)

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
        built.append(manager)
        return manager

    yield build

    for manager in built:
        manager.shutdown()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and not all(m.is_idle for m in built):
        qapp.processEvents()
        time.sleep(0.005)
    assert all(m.is_idle for m in built), "a manager never finished shutting down"


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
    control.setCurrentIndex(control.findData(preset_name))
    listing = staging_list(dialog)
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
    the controls says the thing directly and says it the same on every machine.

    The delegate's contract is one editor for the row being edited, so a paste of any size holds
    **zero** until something opens one.
    """
    dialog = dialogs(managers(entry_point=child_never_returning))
    type_urls(dialog, "\n".join(f"https://many.invalid/{n}" for n in range(SUPPORTED_PASTE)))
    dialog.resolve()

    assert len(dialog.rows) == SUPPORTED_PASTE
    controls = staging_list(dialog).findChildren(QComboBox, ROW_PRESET_NAME)
    assert controls == [], (
        f"{len(controls)} per-row controls exist for {SUPPORTED_PASTE} rows; the delegate builds "
        "one, for the row being edited"
    )


def test_a_four_times_larger_paste_does_not_cost_four_times_more_than_linearly(
    dialogs: Callable[..., AddUrlDialog],
    managers: Callable[..., DownloadManager],
) -> None:
    """**The claim `T118-R10` is really about**, stated as a ratio rather than a clock reading.

    A wall-clock budget says the machine was fast enough. This says the *design* does not grow
    faster than the paste — which is the property that made a hundred and fifty rows cost 0.722 s,
    and the property a delegate buys. Comparing two pastes measured moments apart on one machine
    also removes the runner-speed term, so unlike the bound it replaces this cannot flap between
    two runs of unchanged code.

    A widget per row fails this outright: the cost of building `SUPPORTED_PASTE` controls dwarfs
    the fixed cost that dominates `SMALL_PASTE`, so the ratio runs far past `SCALING_HEADROOM`.
    """

    def cost(count: int) -> float:
        dialog = dialogs(managers(entry_point=child_never_returning))
        urls = "\n".join(f"https://many.invalid/{n}" for n in range(count))
        started = time.monotonic()
        type_urls(dialog, urls)
        dialog.resolve()
        return time.monotonic() - started

    # The small paste first and again, so one-off import and style warm-up lands outside both
    # measurements rather than inside the smaller one, where it would flatter the ratio.
    cost(SMALL_PASTE)
    small = cost(SMALL_PASTE)
    large = cost(SUPPORTED_PASTE)

    assert large < small * SCALING_HEADROOM, (
        f"{SUPPORTED_PASTE} URLs cost {large:.4f}s against {small:.4f}s for {SMALL_PASTE} — a "
        f"factor of {large / small:.1f} for four times the input, over {SCALING_HEADROOM}"
    )


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
