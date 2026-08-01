"""One job, visible: stage, progress, cancel, and what went wrong (`T-017`, `REQ-014`).

The second widget that talks to the download manager, and the first that has to survive a
*stream* of messages rather than a single answer.

## Repaints are coalesced, and the rate is stated

`NFR-001` gives interaction a ~100 ms budget. yt-dlp's progress hook fires far faster than that —
several times a second per fragment, and a fast download is precisely when it fires hardest — so
the obvious implementation, one repaint per message, degrades exactly when there is most to show.

So a message is **recorded** when it arrives and **rendered** on a timer, at most once every
`REPAINT_INTERVAL_MS`. "Does not visibly stutter" is not a testable claim; "at most ten repaints a
second, and the tenth shows the newest message" is, and `tests/ui/test_job_detail.py` asserts it
by watching `pending_progress` and `displayed_progress` separately.

The last message of a burst is never dropped: it is held as pending and rendered by the next tick,
so the final byte count is right even though the intermediate ones were never drawn.

## Retry is a question for the taxonomy, not for this widget

`REQ-018` says a failure is recorded, kept in the queue, and offered a retry. **Not every failure
may be offered one.** `core/errors.py` decides that — `is_retryable` — and this widget asks rather
than deciding, so there is one place where the rule lives and one place to change it.

The case that makes this a correctness rule rather than a tidiness one is `DRM_PROTECTED`
(`SEC-001`, `REQ-EXCL-001`). This project does not work around DRM, and `core/errors.py` states
the consequence in its own words: *offering the button implies a workaround exists*. A retry
button on a DRM failure is a promise the product exists to refuse, so the button is **absent**
rather than disabled — a greyed-out control still says "this is the sort of thing that can be
retried, just not now".

`CANCELLED` is excluded by the same predicate for a different reason: it is not a failure at all
(`ARCHITECTURE.md` §7), and retrying it means starting new work, which is the caller's decision.

## Two sources of truth, and which one answers when

The size a user sees can come from a live progress message or from the durable row, and they do
not agree — deliberately. `manager.py` does not persist progress per message ("an unbounded write
rate for a fact that is worthless after a crash"), so the row lags while a job runs; and the final
byte count arrives with `Succeeded` rather than as a progress update, so the last message lags
once it has finished. Each is right somewhere and wrong elsewhere.

`T017-R4` is what choosing between them ad hoc at each site costs: a helper written for completion
was applied to every terminal state, and cancelling a job at 50% redrew it at the row's stale 10%.
So the rule is written down once, in `_totals_for_ending`, and it has three rows:

| The job is | The size shown comes from | Because |
|---|---|---|
| running | the last rendered progress message | the row does not persist per-message progress |
| `COMPLETED` | the row's `bytes_total` | the final size arrives with the outcome, not as progress |
| `CANCELLED` / `FAILED`, watched | whatever was last shown | the row lags; see below |
| `CANCELLED` / `FAILED`, reopened | the row | nothing was watched, so nothing is closer |

A stopped-partway job takes the last thing shown because the row lags **by design** and the last
message is the closest thing to what actually transferred. Reopening one is the case `T-059`
added: a view that watched none of the download has no earlier display to prefer, so the row —
lagging or not — is the only thing that knows anything.

**Both entry points reach this table through `_adopt_totals`.** They did not, and that is the
whole of `T-059`: `_load` computed its own answer, so the same row gave two results depending on
whether anyone had been watching.

A completed download is its **total**, not its progress counter: the manager writes `bytes_total`
at the terminal transition and leaves `bytes_done` where progress left it, so a real completed row
routinely holds `bytes_done < bytes_total`. Presenting that counter as a final size is how
`Complete: 3 B downloaded` appeared over a file nobody had measured.

## What the view does not own

The retry itself. Re-queueing a failed job is a write, and `ui/` holds no writer — the widget
reports `retry_requested` and composition (`T-036`) performs it, exactly as the add-URL dialog
takes its `JobSink` rather than reaching for SQLite. Cancel is different and does live here:
`DownloadManager.cancel` is not a write, it is a request to a process this manager owns.

`NFR-005` throughout: an accessible name on every control, every state stated in words as well as
shown, and nothing signalled by colour.
"""

from collections.abc import Callable
from contextlib import suppress
from typing import Final, Protocol

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.core.errors import ErrorKind, is_retryable
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import Job
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.downloader.protocol import Progress, Stage

#: The stated maximum repaint rate: ten a second. Comfortably inside `NFR-001`'s ~100 ms
#: interaction budget while being far slower than yt-dlp's hook, which is the whole point.
REPAINT_INTERVAL_MS: Final = 100

#: `REQ-014`'s five stages, in `REQ-014`'s own words. Transcribed from the requirement rather
#: than derived from `Stage`'s member names, so the two are independent statements and a renamed
#: member cannot silently change what the user is told (`ai/TESTING.md` §13).
STAGE_TEXT: Final[dict[Stage, str]] = {
    Stage.PROBING: "Probing",
    Stage.DOWNLOADING_VIDEO: "Downloading video",
    Stage.DOWNLOADING_AUDIO: "Downloading audio",
    Stage.MERGING: "Merging",
    Stage.POST_PROCESSING: "Post-processing",
}

#: What each job status says when no worker is reporting a stage. Terminal states are here
#: because a finished job still has to describe itself: `REQ-018` keeps a failure in the view.
STATUS_TEXT: Final[dict[JobStatus, str]] = {
    JobStatus.QUEUED: "Queued",
    JobStatus.PROBING: "Probing",
    JobStatus.READY: "Ready to download",
    JobStatus.RUNNING: "Downloading",
    JobStatus.POST_PROCESSING: "Post-processing",
    JobStatus.COMPLETED: "Completed",
    JobStatus.FAILED: "Failed",
    JobStatus.CANCELLED: "Cancelled",
}

#: Shown wherever the extractor supplied no number. `None` is not zero — a live stream has no
#: total and a stalled download has no speed, and rendering either as `0` is a confident lie of
#: the kind `Job.progress` already refuses to tell.
UNKNOWN_TEXT: Final = "Unknown"

#: How a cancelled job describes itself when its worker said nothing. Separate from the failure
#: text because `CANCELLED` is not a failure (`ARCHITECTURE.md` §7).
CANCELLED_TEXT: Final = "Cancelled at your request."

#: Labels rendering text this application did not author, forced to `PlainText` (`T016-R6`).
#: An extractor message of `<b>gone</b>` is a message, not markup.
UNTRUSTED_TEXT_LABELS: Final = ("errorMessage", "titleValue")

_BYTE_UNITS: Final = ("B", "KB", "MB", "GB", "TB")


class JobReader(Protocol):
    """The one read this view needs, named as a protocol.

    `ui/` depends on the shape of a repository rather than on `persistence` (`ARCHITECTURE.md`
    §3). `PersistentJobStore` satisfies it, and so does a dictionary in a test.
    """

    def get(self, job_id: str) -> Job | None: ...


def format_bytes(count: int | None) -> str:
    """`1.4 MB`, or `UNKNOWN_TEXT`. Powers of 1024, labelled the way file managers label them."""
    if count is None:
        return UNKNOWN_TEXT
    size = float(count)
    for unit in _BYTE_UNITS:
        if size < 1024 or unit == _BYTE_UNITS[-1]:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    raise AssertionError("unreachable: the loop returns on its last unit")


def format_speed(bytes_per_second: float | None) -> str:
    if bytes_per_second is None:
        return UNKNOWN_TEXT
    return f"{format_bytes(int(bytes_per_second))}/s"


def describe_bar(done: int | None, total: int | None, *, finished: bool) -> str:
    """What the progress bar currently means, in words (`NFR-005`, `T017-R2`).

    **A pure function of the same three values the bar itself is drawn from**, and that is the
    whole design. This finding came back three times — the determinate branch inheriting the
    indeterminate description, `_refresh` writing the bar without one, and completion with an
    unknown total — and each correction added a guard for the case that had just been found while
    leaving the next one to whether anyone thought of it. The cases are not many: `done` and
    `total` are each known or not, and the job is finished or not. Made a function, that space can
    be enumerated by a test rather than sampled by one.

    A finished download is complete whatever the last progress message said, so it reports its
    size rather than a percentage — the final bytes routinely arrive with the outcome instead of
    as a progress update, and "100 percent of 1.0 KB" beside a 2.0 KB file is the stale-byte
    defect wearing a percentage.

    **The finished size is the total, and never `done`** (`T017-R4`). `done` is a progress counter,
    and a progress counter is not a measurement of a finished file: falling back to it turned the
    last stage transition's byte count into a stated final size. With no total there is nothing
    durable saying how big the download was, and "Complete" on its own is the honest answer.
    """
    if finished:
        return f"Complete: {format_bytes(total)} downloaded" if total else "Complete"
    if total:
        return f"{percent_of(done, total)} percent of {format_bytes(total)} downloaded"
    # An unknown total is a real state, not zero percent. `REQ-011`'s indeterminate bar, and this
    # says so in words because the animation alone does not.
    return "Total size unknown; progress cannot be measured"


def totals_for_ending(
    status: JobStatus,
    job: Job | None,
    *,
    last_shown: tuple[int | None, int | None] | None,
) -> tuple[int | None, int | None]:
    """Where a stopped job's size comes from. **The rule, and now the only copy of it.**

    See this module's docstring for the table this implements and why the two sources disagree.

    `T017-R2` established that a *completed* download takes its size from the row, because the
    final bytes arrive with the outcome rather than as progress. `T017-R4` is what came of
    applying that to all three endings without saying so: a job cancelled at 50% was redrawn at
    the row's stale 10%, since the row lags on purpose while a job runs.

    **A free function because `T-079` added a second viewer of the same fact** (`REQ-016`'s queue
    table). `T-059` was one widget reaching this rule from one of the two places that needed it,
    so the same row gave two answers depending on whether anyone had been watching. A table of N
    rows is the third place that has to answer it, and a rule re-derived per surface is the same
    defect with more surfaces.

    `last_shown` is the totals that were last rendered, or `None` when nothing ever was — which
    is the distinction the whole rule turns on. A viewer opened onto a job that had already
    stopped watched none of it, so it has no earlier display to prefer and the row is all there
    is.
    """
    if status is not JobStatus.COMPLETED:
        # Stopped partway. The row does not know how far — progress is not persisted per
        # message — so what was last shown is the closest thing to what actually transferred.
        if last_shown is not None:
            return last_shown
        return (job.bytes_done, job.bytes_total) if job is not None else (None, None)
    total = job.bytes_total if job is not None else None
    if not total:
        # Nothing durable says how big it was, and the progress counter is not a measurement of
        # a finished file. `describe_bar` says "Complete" without inventing a size.
        return (None, None)
    # A completed download **is** its total. `bytes_done` is left wherever progress stopped — the
    # manager writes `bytes_total` at the terminal transition and does not touch the counter — so
    # a real completed row routinely holds `bytes_done < bytes_total`.
    return (total, total)


def percent_of(done: int | None, total: int | None) -> int:
    """How full the bar is, clamped. `0` when there is no total to be a fraction of."""
    if not total:
        return 0
    return int(min((done or 0) / total, 1.0) * 100)


def format_eta(seconds: int | None) -> str:
    """`H:MM:SS`, or `M:SS` under an hour, or `UNKNOWN_TEXT`.

    Deliberately the same function the add-URL dialog renders durations with: two independently
    written clock formatters drift, and a user reading a duration in one panel and an ETA in the
    next should not have to notice which is which.
    """
    from tracks_and_trails.ui.add_dialog import format_duration

    return format_duration(seconds)


class JobProgressView(QWidget):
    """Live progress for exactly one job, with cancel and — where it is honest — retry."""

    #: `(job_id)` — the user asked to retry a failed job. Performed by composition (`T-036`),
    #: because re-queueing is a write and this layer holds no writer.
    retry_requested = Signal(str)

    def __init__(
        self,
        *,
        manager: DownloadManager,
        jobs: JobReader,
        job_id: str,
        parent: QWidget | None = None,
        repaint_interval_ms: int = REPAINT_INTERVAL_MS,
    ) -> None:
        super().__init__(parent)
        self._manager = manager
        self._jobs = jobs
        self._job_id = job_id

        #: The newest message that has arrived but not yet been drawn. See the module docstring.
        self._pending: Progress | None = None
        #: The message the fields currently show.
        self._displayed: Progress | None = None
        #: How many times the progress fields have been redrawn. See `renders`.
        self._renders = 0
        self._status = JobStatus.QUEUED
        #: The last totals the bar was drawn from, so completion can redraw it truthfully
        #: without a second method reaching into the bar (`T017-R2`).
        self._totals: tuple[int | None, int | None] = (None, None)
        #: The classified failure and its verbatim text. The kind is `None` when the signal
        #: carried something this widget cannot classify — see `_on_job_failed`.
        self._failure: tuple[ErrorKind | None, str] | None = None

        self.setObjectName("jobProgressView")
        self._build()

        self._repaint = QTimer(self)
        self._repaint.setInterval(repaint_interval_ms)
        self._repaint.timeout.connect(self._draw_pending)

        self._connect_manager()
        self._load()

    # --- construction -------------------------------------------------------------------

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        self._title = QLabel(self)
        self._title.setObjectName("titleValue")
        self._title.setAccessibleName("Job")
        self._title.setWordWrap(True)
        layout.addWidget(self._title)

        self._stage = QLabel(self)
        self._stage.setObjectName("stageValue")
        self._stage.setAccessibleName("Current stage")
        layout.addWidget(self._stage)

        self._bar = QProgressBar(self)
        self._bar.setObjectName("progressBar")
        self._bar.setAccessibleName("Download progress")
        self._bar.setTextVisible(True)
        layout.addWidget(self._bar)

        layout.addWidget(self._build_numbers())

        self._error = QLabel(self)
        self._error.setObjectName("errorMessage")
        self._error.setAccessibleName("Error message")
        self._error.setWordWrap(True)
        # Selectable so a user can copy an extractor message into a search or a bug report. A
        # message kept verbatim (`NFR-006`) that cannot be copied is only half of the point.
        self._error.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self._error.setVisible(False)
        layout.addWidget(self._error)

        layout.addWidget(self._build_actions())

        for name in UNTRUSTED_TEXT_LABELS:
            label = self.findChild(QLabel, name)
            if label is not None:
                label.setTextFormat(Qt.TextFormat.PlainText)

    def _build_numbers(self) -> QWidget:
        box = QGroupBox("Progress", self)
        box.setObjectName("progressNumbers")
        form = QFormLayout(box)
        self._bytes = self._field(box, "bytesValue", "Downloaded of total")
        self._speed = self._field(box, "speedValue", "Speed")
        self._eta = self._field(box, "etaValue", "Estimated time remaining")
        form.addRow("Downloaded:", self._bytes)
        form.addRow("Speed:", self._speed)
        form.addRow("ETA:", self._eta)
        return box

    def _field(self, parent: QWidget, name: str, accessible: str) -> QLabel:
        label = QLabel(parent)
        label.setObjectName(name)
        label.setAccessibleName(accessible)
        label.setText(UNKNOWN_TEXT)
        return label

    def _build_actions(self) -> QWidget:
        row = QWidget(self)
        row.setObjectName("jobActions")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)

        self._cancel_button = QPushButton("&Cancel", row)
        self._cancel_button.setObjectName("cancelJobButton")
        self._cancel_button.setAccessibleName("Cancel this download")
        self._cancel_button.clicked.connect(self.cancel)
        layout.addWidget(self._cancel_button)

        self._retry_button = QPushButton("&Retry", row)
        self._retry_button.setObjectName("retryJobButton")
        self._retry_button.setAccessibleName("Retry this download")
        self._retry_button.clicked.connect(lambda: self.retry_requested.emit(self._job_id))
        layout.addWidget(self._retry_button)

        layout.addStretch(1)
        return row

    def _connect_manager(self) -> None:
        self._manager.progress.connect(self._on_progress)
        self._manager.job_changed.connect(self._on_job_changed)
        self._manager.job_failed.connect(self._on_job_failed)
        self._manager.job_succeeded.connect(self._on_job_succeeded)

    def detach(self) -> None:
        """Stop listening to the manager. **Called before a view is replaced** (`T-036`).

        Qt drops a connection when its receiver is destroyed, but `deleteLater` is asynchronous,
        so a view swapped out mid-download would go on answering signals for however many event
        loop turns it took to die. With a pool of one that is not a leak, it is a *second*
        listener — and `T-036` has to assert that every manager signal the UI needs has exactly
        one connection, because a signal connected twice is how one queued job becomes two rows.

        Safe to call more than once: a disconnect of something already disconnected raises, and
        being asked twice to stop listening is not an error worth propagating out of a slot.
        """
        for signal, slot in (
            (self._manager.progress, self._on_progress),
            (self._manager.job_changed, self._on_job_changed),
            (self._manager.job_failed, self._on_job_failed),
            (self._manager.job_succeeded, self._on_job_succeeded),
        ):
            with suppress(RuntimeError):
                signal.disconnect(slot)
        self._repaint.stop()

    # --- queries used by callers and tests -----------------------------------------------

    @property
    def job_id(self) -> str:
        return self._job_id

    @property
    def pending_progress(self) -> Progress | None:
        """The newest message that has arrived and has **not** been drawn yet.

        Public because the coalescing rule is a promise rather than an implementation detail:
        `REPAINT_INTERVAL_MS` bounds how often the fields change, and this is how a test tells
        "coalesced" from "dropped" (`T-017` acceptance criteria).
        """
        return self._pending

    @property
    def displayed_progress(self) -> Progress | None:
        """The message the fields currently show."""
        return self._displayed

    @property
    def renders(self) -> int:
        """How many times the progress fields have been redrawn (`T017-R1`).

        Public for the same reason `pending_progress` is: `REPAINT_INTERVAL_MS` is a promise
        about *this number*, and a promise nothing can count is not one. The first version of
        the burst test counted messages the widget had absorbed, which is a different quantity —
        it stayed at zero while a second route was redrawing on every status change.
        """
        return self._renders

    @property
    def status(self) -> JobStatus:
        return self._status

    @property
    def _is_terminal(self) -> bool:
        """Whether the job has ended. Asked by the repaint rule as well as by the rendering."""
        return self._status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)

    @property
    def failure(self) -> tuple[ErrorKind | None, str] | None:
        """The classified failure and its verbatim message, if the job failed."""
        return self._failure

    @property
    def can_cancel(self) -> bool:
        return self._cancel_button.isEnabled()

    @property
    def can_retry(self) -> bool:
        """Whether a retry is offered at all — **absent**, not merely disabled, when it is not.

        `is_retryable` decides (`REQ-018`), so `DRM_PROTECTED` never reaches this as `True`
        (`SEC-001`). A disabled button would still assert that a retry exists somewhere, which
        for DRM is precisely the claim `REQ-EXCL-001` refuses to make.
        """
        return not self._retry_button.isHidden()

    def stage_text(self) -> str:
        return self._stage.text()

    def error_text(self) -> str:
        return self._error.text()

    def focus_chain(self) -> list[QWidget]:
        """Every keyboard-focusable control, in its intended order (`NFR-005`)."""
        return [self._error, self._cancel_button, self._retry_button]

    # --- actions ------------------------------------------------------------------------

    def cancel(self) -> None:
        """Ask the manager to stop this job (`REQ-015`). **Returns immediately.**

        Cancellation escalates on the manager's own timer and reaps the worker's whole process
        tree (`T-019`); nothing here waits for any of it.
        """
        self._manager.cancel(self._job_id)

    # --- manager signals ----------------------------------------------------------------

    def _on_progress(self, message: object) -> None:
        """Record the newest message. Drawing it is the timer's job — see the module docstring."""
        if not isinstance(message, Progress) or message.job_id != self._job_id:
            return
        self._pending = message
        if not self._repaint.isActive():
            self._repaint.start()

    def _draw_pending(self) -> None:
        pending, self._pending = self._pending, None
        if pending is None:
            # A quiet interval: stop the timer rather than tick forever behind a finished job.
            self._repaint.stop()
            return
        self._displayed = pending
        self._show_progress(pending)

    def _on_job_changed(self, job_id: str, status: str) -> None:
        """A state change is the newer fact, and is shown at once — but it is not progress.

        **It does not flush pending progress** (`T017-R1`). It used to call `_draw_pending()`,
        which is a second route into `_show_progress` with no rate limit on it: interleaving
        three progress messages with three status changes redrew three times inside one
        interval, and the promise this widget makes is about that number.

        **What is immediate is an *ending*, not every state word** (`T017-R3`, correcting an
        overclaim in the previous version of this docstring). `_refresh` writes the stage line
        itself when the job has finished or when no progress has been drawn yet, so a cancelled
        job never goes on saying "Downloading" — that is the case a user must not be lied to
        about. While a job is *running*, a status change leaves the stage line showing the more
        specific thing a worker reported: "Downloading video" is better information than
        "Downloading", and it is replaced by the next repaint within `REPAINT_INTERVAL_MS`. The
        earlier wording claimed all state words were immediate, which was true only before
        anything had been rendered.

        At a terminal state the pending message is **dropped** rather than deferred. Nothing a
        worker said before the end can still be true afterwards, and drawing it a tick later
        would overwrite the ending with the download that is no longer happening.

        **`QUEUED` retires the last attempt's message** (`T079-R1`, found in the queue table and
        audited back to here — this widget had it too). `REQ-018`'s retry edge is
        `FAILED → QUEUED`, and a job in `QUEUED` has no worker, so a drawn message belongs to the
        attempt that failed. Without this, pressing Retry left the stage line saying "Downloading
        video" at the failed attempt's percentage, speed and ETA, because `_refresh` only rewrites
        the stage line when the job is terminal *or* nothing has been drawn — and after a failure
        something had been drawn.

        The boundary is the status rather than `Job.attempts`: nothing in this project increments
        that column, so keying to it would be comparing `0` with `0` for ever.
        """
        if job_id != self._job_id:
            return
        self._status = JobStatus(status)
        if self._is_terminal:
            self._pending = None
            self._repaint.stop()
            self._adopt_totals()
        elif self._status is JobStatus.QUEUED:
            self._pending = None
            self._displayed = None
            self._totals = (None, None)
            # The failure belonged to the attempt that ended, and `failure` is public: a queued
            # job reporting the previous attempt's error is the same lie one field over.
            self._failure = None
            # **The labels too, not only the state behind them.** Dropping `_displayed` is not
            # enough: `_refresh` never writes speed or ETA — only `_show_progress` does — so a
            # re-queued job went on showing `2.1 MB/s` and a 42-second estimate for a download
            # that had stopped. Found by the test for this correction, not by inspection.
            self._speed.setText(UNKNOWN_TEXT)
            self._eta.setText(UNKNOWN_TEXT)
            self._adopt_totals()
        self._refresh()

    def _adopt_totals(self) -> None:
        """Put the byte counts where the rule says they come from. **The one entry point.**

        `T-059`. `T-017` put the rule in `_totals_for_ending` and then reached it from one of the
        two places that need it: a job that finished *while the view was watching* went through it,
        and a view *opened onto* a finished job did not. Opening one is not an exotic path — it is
        what happens after every restart, and after `T-036` it is how any completed job first
        appears — so the same row of the same table gave two different answers depending on
        whether anyone had been looking.

        Both callers arrive here now. A running job takes the row, because nothing has been
        rendered yet that could be closer to the truth.
        """
        if self._is_terminal:
            self._show_totals(*self._totals_for_ending())
            return
        job = self._jobs.get(self._job_id)
        if job is not None:
            self._show_totals(job.bytes_done, job.bytes_total)

    def _totals_for_ending(self) -> tuple[int | None, int | None]:
        """This view's ending totals, from the shared rule (`totals_for_ending`).

        The rule moved out of this class when `T-079` gave it a second caller; what stays here is
        the translation of *this* widget's state into the rule's arguments. `last_shown` is the
        pair the bar was last drawn from, and `None` when nothing has been drawn at all — the
        distinction `T017-R4`'s second half turns on.

        Reading the row here is a `T-016` guarantee rather than an assumption: `job_changed` is
        emitted from the write's own completion callback, so the row really does hold this state.
        """
        return totals_for_ending(
            self._status,
            self._jobs.get(self._job_id),
            last_shown=self._totals if self._displayed is not None else None,
        )

    def _on_job_failed(self, job_id: str, kind: object, message: str) -> None:
        """Show the extractor's message **verbatim** (`REQ-005`, `NFR-006`).

        Not summarised, not paraphrased, and not folded into a sentence that changes it. The
        classification is shown beside it rather than instead of it: the kind decides whether a
        retry is offered, and the text is the only thing that says what happened.
        """
        if job_id != self._job_id:
            return
        # **An unclassifiable kind is not classified.** There is no fallback member to reach for
        # and inventing one would be a guess about retry policy, which `core/errors.py` already
        # rules out: *a wrong guess is worse than no guess, because `DRM_PROTECTED` and `NETWORK`
        # carry retry policy*. So the message is shown and no retry is offered.
        self._failure = (kind if isinstance(kind, ErrorKind) else None, message)
        self._refresh()

    def _on_job_succeeded(self, job_id: str, _output_path: str) -> None:
        if job_id != self._job_id:
            return
        self._refresh()

    # --- rendering ----------------------------------------------------------------------

    def _load(self) -> None:
        job = self._jobs.get(self._job_id)
        if job is not None:
            self._status = job.status
            self._title.setText(job.title or job.url)
            if job.error_kind is not None and job.status in (JobStatus.FAILED, JobStatus.CANCELLED):
                self._failure = (job.error_kind, job.error_message or "")
        self._adopt_totals()
        self._refresh()

    def _show_progress(self, message: Progress) -> None:
        self._renders += 1
        self._stage.setText(STAGE_TEXT.get(message.stage, STATUS_TEXT[self._status]))
        self._show_totals(message.downloaded_bytes, message.total_bytes)
        self._speed.setText(format_speed(message.speed_bytes_per_second))
        self._eta.setText(format_eta(message.eta_seconds))

    def _show_totals(self, done: int | None, total: int | None) -> None:
        """Write the byte counts, and hand the bar to the one method that owns it."""
        self._totals = (done, total)
        # "Unknown of Unknown" is noise; one word says the same thing. Reachable only from a
        # completed download whose size nothing durable recorded (`_totals_for_ending`).
        self._bytes.setText(
            UNKNOWN_TEXT
            if done is None and total is None
            else f"{format_bytes(done)} of {format_bytes(total)}"
        )
        self._draw_bar(done, total)

    def _draw_bar(self, done: int | None, total: int | None, *, finished: bool = False) -> None:
        """**The only place the progress bar is written**, range, value and words together.

        `T017-R2`, twice. The first version set an accessible description in the indeterminate
        branch and never cleared it, so a bar that became determinate showed 50% while telling a
        screen reader that progress could not be measured. The correction wrote the description
        in both branches of *this* computation — and missed that `_refresh` set the bar to 100%
        on completion through a path of its own, which left "50 percent of 10 B downloaded"
        standing over a full bar.

        Two methods writing one widget's state independently is what produced the same defect
        twice, so there are no longer two. `_refresh` asks for a finished bar rather than
        setting one, and a description is not something a caller can forget to update, because
        no caller writes the value either.

        Under `NFR-005` the contradiction is worse than silence: sighted and screen-reader users
        were being told different things about the same download.
        """
        if finished or total:
            self._bar.setRange(0, 100)
            self._bar.setValue(100 if finished else percent_of(done, total))
        else:
            self._bar.setRange(0, 0)
        self._bar.setAccessibleDescription(describe_bar(done, total, finished=finished))

    def _refresh(self) -> None:
        """Put the whole widget in the state its job is in. **Every state in words.**

        `NFR-005` forbids conveying state by appearance alone, so the stage line always says
        what is happening — including for the three endings, which no progress message ever
        describes because there is no worker left to describe them.
        """
        terminal = self._is_terminal
        if terminal or self._displayed is None:
            self._stage.setText(STATUS_TEXT[self._status])

        if self._status is JobStatus.COMPLETED:
            self._draw_bar(*self._totals, finished=True)

        failure = self._failure
        if self._status is JobStatus.CANCELLED:
            # A cancellation is shown as one, and never as an error (`ARCHITECTURE.md` §7). The
            # worker's own words are used when it managed to send them, because they are the
            # evidence that the cooperative path ran.
            #
            # *(This ended "and left partial files in a known state". `T046-R1` moved the download
            # into a staging directory that is discarded whatever the outcome, so a cancelled job
            # leaves no partial file at all — `T046-R3`.)*
            spoken = failure[1] if failure is not None else ""
            self._error.setText(spoken or CANCELLED_TEXT)
            self._error.setVisible(True)
        elif failure is not None and self._status is JobStatus.FAILED:
            kind, message = failure
            self._error.setText(f"{kind.value}\n{message}" if kind is not None else message)
            self._error.setVisible(True)
        else:
            self._error.setVisible(False)

        self._cancel_button.setEnabled(not terminal)
        # **Absent, not disabled** — see `can_retry`. The predicate is `is_retryable`, never a
        # comparison against a kind spelled out here: a second non-retryable kind must become
        # unofferable by being added to `core/errors.py`, not by being remembered in a widget.
        offer = (
            self._status is JobStatus.FAILED
            and failure is not None
            and failure[0] is not None
            and is_retryable(failure[0])
        )
        self._retry_button.setVisible(offer)


def build_progress_view(
    manager: DownloadManager, jobs: JobReader, job_id: str, retry: Callable[[str], None] | None
) -> JobProgressView:
    """Construct a view and connect its retry to whatever composition supplies (`T-036`).

    A named function rather than three lines at the call site, because "who performs the retry"
    is the one wiring decision this widget deliberately does not make, and burying it in
    composition is how it would come to be forgotten.
    """
    view = JobProgressView(manager=manager, jobs=jobs, job_id=job_id)
    if retry is not None:
        view.retry_requested.connect(retry)
    return view
