"""A row's verbs reach the same destinations the toolbar's do (`UX-005` §4, `T-124`).

`tests/ui/test_row_verbs.py` proves *which* verbs a state offers. This file proves that activating
one does something — and does the **same** thing the existing route does, rather than a second
implementation of it.

**Why that distinction is the whole file.** `T-016`'s record is an action that appeared to work
and quietly did nothing; `UX-005` §4 adds a second route to five effects that already had one, and
two routes to one effect is how one of them ends up with a guard the other lacks. So every test
below asserts the destination, not the signal.
"""

import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QAccessible, QContextMenuEvent, QFontMetrics, QImage, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QMenu,
    QMessageBox,
    QStyleOptionViewItem,
    QToolBar,
    QToolButton,
)

from tracks_and_trails.core import presets
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import DownloadRequest, Job
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.ui import theme
from tracks_and_trails.ui.format_text import FORMAT_PREFIX
from tracks_and_trails.ui.job_detail import UNKNOWN_TEXT
from tracks_and_trails.ui.main_window import (
    JUST_THIS_ITEM,
    MainWindow,
)
from tracks_and_trails.ui.queue_view import PROGRESS_COLUMN
from tracks_and_trails.ui.row_delegate import (
    CHOOSE_FORMATS_TEXT,
    DETAIL_ROLE,
    INHERITED_SUFFIX,
    OPTIONS_TEXT,
    PADDING,
    PRESET_CHOICES_ROLE,
    PRESET_ROLE,
    ROW_PRESET_NAME,
    SELECTOR_ROLE,
    STATE_CHIP_ROLE,
    RowDelegate,
)
from tracks_and_trails.ui.row_verbs import LABELS, Verb


class _FakeQueue:
    """A `QueueReader` over a fixed list, in the order a table would show them."""

    def __init__(self, jobs: list[Job]) -> None:
        self._jobs = jobs

    def get(self, job_id: str) -> Job | None:
        return next((job for job in self._jobs if job.id == job_id), None)

    def all_jobs(self) -> list[Job]:
        return list(self._jobs)


class _EmptyJobStore:
    """The narrowest thing `DownloadManager` will accept; nothing here starts a job."""

    def get(self, job_id: str) -> Job | None:
        return None

    def all_jobs(self) -> list[Job]:
        return []


def _job(job_id: str, position: int, status: JobStatus = JobStatus.QUEUED) -> Job:
    request = DownloadRequest(
        url="https://example.invalid/clip",
        output_directory="/downloads",
        format_selector="best",
        output_template="%(title)s.%(ext)s",
    )
    return Job(id=job_id, url=request.url, request=request, status=status, queue_position=position)


class _RecordingSink:
    """A `JobSink` that accepts and remembers, so `T-016` leaves Add URLs enabled."""

    def __init__(self) -> None:
        self.submitted: list[Any] = []

    def submit(self, jobs: Any, done: Any) -> None:
        self.submitted.extend(jobs)
        done(None)


def _window_over(jobs: list[Job], tmp_path: Path, **handlers: Any) -> MainWindow:
    manager = DownloadManager(_EmptyJobStore(), concurrency=1)  # type: ignore[arg-type]
    manager.start_queue()
    return MainWindow(
        geometry_file=tmp_path / "window.toml",
        concurrency=1,
        control_bar=True,
        manager=manager,
        queue=_FakeQueue(jobs),
        **handlers,
    )


# --- the five that are writes, and the one that is not ------------------------------------


def test_a_rows_cancel_reaches_the_manager(qapp: QApplication, tmp_path: Path) -> None:
    """Cancel is the one verb the view performs itself (`ARCHITECTURE.md` §7).

    It asks the manager to stop a session the manager owns, which is not a write — so it needs no
    composition callback and must work on a window that was given none. A `Cancel` that silently
    required a handler nobody wired would be the `T-016` failure again.
    """
    window = _window_over([_job("job-1", 0, JobStatus.RUNNING)], tmp_path)
    view = window.queue_view
    assert view is not None
    asked: list[str] = []
    # Replaced on the instance, not the class: the next test gets its own manager, and a class
    # patch would outlive this one.
    view._manager.cancel = asked.append  # type: ignore[assignment]

    view.trigger_verb("job-1", Verb.CANCEL)

    assert asked == ["job-1"], (
        "a running row's Cancel did not reach the manager, so a user watching a download they "
        "want stopped has no way to stop it"
    )


@pytest.mark.parametrize(
    ("verb", "handler", "status"),
    [
        (Verb.REMOVE, "on_remove_requested", JobStatus.QUEUED),
        (Verb.RETRY, "retry", JobStatus.FAILED),
    ],
)
def test_a_rows_write_verb_reaches_the_handler_composition_supplied(
    qapp: QApplication, tmp_path: Path, verb: Verb, handler: str, status: JobStatus
) -> None:
    """`ui/` holds no writer, so these are reported and composition performs them."""
    asked: list[str] = []
    window = _window_over([_job("job-1", 0, status)], tmp_path, **{handler: asked.append})

    view = window.queue_view
    assert view is not None
    view.trigger_verb("job-1", verb)

    assert asked == ["job-1"], f"the row's {verb.value} never reached {handler}"


def test_a_rows_move_hands_over_the_whole_new_order(qapp: QApplication, tmp_path: Path) -> None:
    """`T-081`: the repository redeals positions, so the caller sends the arrangement.

    Asserted as the resulting *order* rather than as "move was called", because a delta would be
    the repository inferring an arrangement it did not choose — and because the row's ↑ has to
    produce the same list the toolbar's does.
    """
    orders: list[list[str]] = []
    window = _window_over(
        [_job("job-1", 0), _job("job-2", 1), _job("job-3", 2)],
        tmp_path,
        on_reorder_requested=orders.append,
    )
    view = window.queue_view
    assert view is not None

    view.trigger_verb("job-2", Verb.MOVE_UP)

    assert orders == [["job-2", "job-1", "job-3"]], (
        f"the row's ↑ produced {orders}, which is not job-2 moved one place up"
    )


def test_a_rows_file_verb_goes_through_file_actions(qapp: QApplication, tmp_path: Path) -> None:
    """`REQ-021` and `SEC-001`: containment lives in `FileActions` and nowhere else.

    **Asserted by which object acted, not by whether a file opened.** A row that resolved its own
    path would be a second place the containment check could be missing — and the check is the
    only reason opening a file from a queue is safe at all. So the test's subject is that the row
    reached `FileActions`, because that is what carries the guarantee.
    """
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    window = _window_over(
        [_job("job-1", 0, JobStatus.COMPLETED)], tmp_path, output_directory=downloads
    )
    view = window.queue_view
    assert view is not None
    actions = next(each for each in window.file_actions if each.table is view.table)
    opened: list[str] = []
    actions.open_selected = lambda *_: opened.append("open")  # type: ignore[method-assign]

    view.trigger_verb("job-1", Verb.OPEN)

    assert opened == ["open"], (
        "the row's Open did not go through FileActions, so it either did nothing or opened a "
        "path nobody checked was inside the download directory"
    )


# --- the overflow, which is also the keyboard route ----------------------------------------


def test_the_overflow_menu_holds_exactly_what_the_row_offers(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`UX-005` §4. The **keyboard** menu holds everything the state permits.

    A menu built from its own table would be a second opinion about what a row offers, and the
    first time the two differed the user would be offered something the row had already decided
    against.

    **This is the Menu-key and right-click route specifically** (`T-135`). It was the only route
    when this was written, and the `⋯` now holds the narrower set — what the row could not draw.
    What must not vary with the window's width is *this* one: a keyboard menu that offered less on
    a maximised window would make the declared route depend on the pointer's world.
    """
    window = _window_over([_job("job-1", 0, JobStatus.FAILED)], tmp_path, retry=lambda _: None)
    queue = window.queue_view
    assert queue is not None
    menu = window._show_row_menu("job-1", queue.verbs_of("job-1"))
    assert isinstance(menu, QMenu)
    try:
        labels = [action.text() for action in menu.actions()]
        view = window.queue_view
        assert view is not None
        assert labels == [LABELS[verb] for verb in view.verbs_of("job-1")], (
            f"the overflow lists {labels} where the row offers "
            f"{[LABELS[v] for v in view.verbs_of('job-1')]}"
        )
    finally:
        menu.close()


def test_the_overflow_takes_the_same_route_a_click_takes(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`NFR-005`: the keyboard reaches what the pointer reaches — *the same way*.

    If the menu emitted the shell's signals itself, the two routes would be two implementations of
    one action and would differ the first time either gained a guard. Asserted by triggering the
    menu action and checking the composition handler saw it, which is the same destination
    `test_a_rows_write_verb_reaches_the_handler_composition_supplied` checks for a click.
    """
    asked: list[str] = []
    window = _window_over([_job("job-1", 0, JobStatus.FAILED)], tmp_path, retry=asked.append)
    queue = window.queue_view
    assert queue is not None
    menu = window._show_row_menu("job-1", queue.verbs_of("job-1"))
    assert isinstance(menu, QMenu)
    try:
        retry = next(a for a in menu.actions() if a.objectName() == f"rowVerb_{Verb.RETRY.value}")
        retry.trigger()
    finally:
        menu.close()

    assert asked == ["job-1"], "the overflow's Retry did not reach the handler a click reaches"


def test_a_row_the_queue_does_not_hold_offers_no_menu(qapp: QApplication, tmp_path: Path) -> None:
    """An id with no row has no verbs, so there is nothing to pop up.

    A menu built anyway would be empty, and an empty menu appearing under the pointer reads as a
    broken control rather than as "this row is gone".
    """
    window = _window_over([_job("job-1", 0)], tmp_path)
    queue = window.queue_view
    assert queue is not None
    assert window._show_row_menu("job-missing", queue.verbs_of("job-missing")) is None


def test_the_drawn_verbs_are_where_the_click_is_tested(qapp: QApplication, tmp_path: Path) -> None:
    """One geometry, shared by the paint and the hit test (`T118-R12`'s lesson, restated).

    A button drawn in one place and hit-tested in another is a control that works where nobody
    clicks. `_verb_rects` is the single definition; this asserts the rects it hands the painter
    are inside the row and in the order the row draws them, right to left.
    """
    window = _window_over([_job("job-1", 0, JobStatus.QUEUED)], tmp_path)
    view = window.queue_view
    assert view is not None
    view.table.resize(700, 300)
    delegate = view.table.itemDelegate()
    assert isinstance(delegate, RowDelegate)

    index = view.model.index(0, 0)
    body = QRect(0, 0, 700, 66).adjusted(PADDING, PADDING, -PADDING, -PADDING)
    area = QRect(body.left() + 100, body.top(), body.width() - 100, body.height())
    placed = delegate._verb_rects(QFontMetrics(view.table.font()), area, body, index)

    assert placed, "a queued row drew no verbs at all"
    for _, rect in placed:
        assert body.contains(rect.topLeft()) and rect.right() <= area.right(), (
            f"a verb was placed at {rect}, outside the row body {body}"
        )
    rights = [rect.right() for _, rect in placed]
    assert rights == sorted(rights, reverse=True), (
        f"the verbs were not laid out right to left: {rights}"
    )
    assert not any(
        placed[i][1].intersects(placed[j][1])
        for i in range(len(placed))
        for j in range(i + 1, len(placed))
    ), "two verbs overlap, so one of them is drawn where the other is clicked"


def test_the_overflow_keeps_its_place_as_the_state_changes(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`UX-005` §4 accepts that the buttons shift; the `⋯` must not.

    It is laid out first — rightmost — so every other verb moves around it, and a control that
    relocated as a download progressed would be one the user has to re-find on every repaint.

    **Measured at a width narrow enough for the `⋯` to exist** (`T-135`). It used to be drawn
    unconditionally, and this test took a 700px row and simply expected one; under `UX-005` row 8
    the button appears only when the row could not show everything, so a wide row now legitimately
    has none and `next(...)` raised `StopIteration` rather than failing an assertion.
    """
    window = _window_over(
        [_job("job-1", 0, JobStatus.QUEUED), _job("job-2", 1, JobStatus.RUNNING)], tmp_path
    )
    view = window.queue_view
    assert view is not None
    delegate = view.table.itemDelegate()
    assert isinstance(delegate, RowDelegate)
    metrics = QFontMetrics(view.table.font())
    body = QRect(0, 0, 700, 66).adjusted(PADDING, PADDING, -PADDING, -PADDING)

    def overflow_at(width: int, row: int) -> QRect | None:
        area = QRect(body.left(), body.top(), width, body.height())
        placed = delegate._verb_rects(metrics, area, body, view.model.index(row, 0))
        return next((rect for verb, rect in placed if verb is None), None)

    # **The width is searched for rather than written down.** A queued row offers three verbs and
    # a running one offers a single Cancel, so the band where *both* drop something is narrow and
    # moves with the font — a literal here would be a number that passed on this machine.
    places: list[QRect] = []
    for width in range(24, 200, 2):
        found = [overflow_at(width, row) for row in (0, 1)]
        if all(rect is not None for rect in found):
            places = [rect for rect in found if rect is not None]
            break
    assert len(places) == 2, (
        "no width between 24 and 200 gave both a queued and a running row an overflow, so this "
        "measures nothing; the layout or the verb sets have changed shape"
    )

    assert places[0] == places[1], (
        f"the overflow sat at {places[0]} on a queued row and {places[1]} on a running one; it "
        "is the keyboard route, and a route that moves with the job's state is not one"
    )


def test_the_verbs_leave_the_message_its_width(qapp: QApplication, tmp_path: Path) -> None:
    """`NFR-006` and `UX-005` §4: the buttons take the last line, never the message's.

    The reason the verbs share the third line rather than taking a gutter is that a gutter narrows
    the title and the extractor's verbatim message on *every* row, including the ones with no
    verbs at all. This asserts the trade actually holds.
    """
    window = _window_over([_job("job-1", 0, JobStatus.QUEUED)], tmp_path)
    view = window.queue_view
    assert view is not None
    delegate = view.table.itemDelegate()
    assert isinstance(delegate, RowDelegate)
    metrics = QFontMetrics(view.table.font())
    body = QRect(0, 0, 700, 66).adjusted(PADDING, PADDING, -PADDING, -PADDING)
    area = QRect(body.left() + 100, body.top(), body.width() - 100, body.height())

    placed = delegate._verb_rects(metrics, area, body, view.model.index(0, 0))
    assert placed
    line = metrics.height()
    first_two_lines = QRect(area.left(), area.top(), area.width(), 2 * line)
    for verb, rect in placed:
        assert not rect.intersects(first_two_lines), (
            f"{verb} was drawn over the row's first two lines, which carry the title and the "
            "extractor's message — the whole reason UX-005 put the verbs on the last line"
        )


# --- the window itself (`UX-005` §1 and §2) -------------------------------------------------


def test_selecting_a_row_opens_nothing(qapp: QApplication, tmp_path: Path) -> None:
    """`UX-005` §2: there is no detail pane, and selecting a row does not produce one.

    The window used to grow a `JobProgressView` in the splitter's lower pane on selection. The row
    carries what a user needs to know, and a second surface repeating it is a second place for it
    to disagree — which is the failure `T-059` and `T017-R2` both record in other forms.
    """
    from tracks_and_trails.ui.job_detail import JobProgressView

    window = _window_over([_job("job-1", 0)], tmp_path)
    view = window.queue_view
    assert view is not None

    assert view.select("job-1")

    assert window.findChildren(JobProgressView) == [], (
        "selecting a row built a detail view; UX-005 removed the pane and the row is what reports"
    )
    assert not hasattr(window, "watch"), (
        "the window still offers watch(); the pane it opened is gone, so the route to it should "
        "be too rather than left as a way to build an orphan widget"
    )


# --- UX-005 §6: the format control, only while retarget() would accept it -------------------


@pytest.mark.parametrize(
    ("status", "offered"),
    [
        (JobStatus.QUEUED, True),
        (JobStatus.READY, True),
        (JobStatus.PROBING, False),
        (JobStatus.RUNNING, False),
        (JobStatus.POST_PROCESSING, False),
        (JobStatus.COMPLETED, False),
        (JobStatus.FAILED, False),
        (JobStatus.CANCELLED, False),
    ],
)
def test_the_format_control_appears_exactly_while_retarget_accepts(
    qapp: QApplication, tmp_path: Path, status: JobStatus, offered: bool
) -> None:
    """`UX-005` §6, and `Job.RETARGETABLE` is the authority.

    **Every status, not just the two that should offer it.** The dangerous half is a control on a
    row the manager would refuse: `retarget` declines a job past `RETARGETABLE`, and it declines
    *silently* by design — it reports through `otherwise` rather than raising, because a job that
    started while a dialog was open is ordinary. So a control drawn on a running row would take
    the user's choice, change nothing, and leave them believing the format changed. That is
    `UX-005` §5's rule with the worst possible consequence, which is why the parametrize covers
    all eight.

    Transcribed from `Job.RETARGETABLE`'s *specification* — "legal only before a worker has acted
    on it" — rather than read from the frozenset, so shrinking that set fails here (`T034-R4`).
    """
    window = _window_over([_job("job-1", 0, status)], tmp_path)
    view = window.queue_view
    assert view is not None
    choices = view.model.data(view.model.index(0, 0), PRESET_CHOICES_ROLE)

    assert bool(choices) is offered, (
        f"a {status.value} row {'offers no' if offered else 'offers a'} format control; "
        "UX-005 §6 puts it on exactly the rows retarget() would accept, and a control on any "
        "other row takes a choice that is silently discarded"
    )


def test_choosing_a_format_goes_through_retarget(qapp: QApplication, tmp_path: Path) -> None:
    """`T036-R1`: the manager owns the write, because the manager is what announces it.

    Composition once wrote a status change through the store directly; nothing emitted
    `job_changed`, and a view went on showing a state the row no longer held. A request change has
    the same shape. Asserted by **which object was asked**, not by the row's appearance.
    """
    window = _window_over([_job("job-1", 0, JobStatus.QUEUED)], tmp_path)
    view = window.queue_view
    assert view is not None
    asked: list[tuple[str, str]] = []
    assert window._manager is not None
    window._manager.retarget = (  # type: ignore[method-assign]
        lambda job_id, request, **_: asked.append((job_id, request.format_selector))
    )

    assert view.model.setData(view.model.index(0, 0), "Audio only (MP3)", PRESET_ROLE)

    assert len(asked) == 1 and asked[0][0] == "job-1", f"retarget was asked {asked}"
    assert asked[0][1] == presets.by_name("Audio only (MP3)").format_selector, (
        f"the request sent to retarget carries {asked[0][1]!r}, which is not the selector the "
        "preset the user picked actually means"
    )


def test_a_row_reports_the_preset_its_request_already_is(
    qapp: QApplication, tmp_path: Path
) -> None:
    """The control shows the row's current choice, not a blank (`T118-R4`'s lesson, restated).

    **Asserted with a preset that shares its selector with another**, which is what makes this a
    test rather than a coincidence. `Audio only (MP3)` and `Audio only (original)` both use
    `bestaudio/best`, as do `Best video available` and `Video with embedded subtitles`; matching on
    the selector alone returns whichever is defined first, so a test using the *first* of a pair
    passes against exactly the defect it is meant to catch. It did — a reviewer mutation reducing
    the comparison to `format_selector` survived until this used the second one.

    So: every field a preset owns is compared, because two presets differing only in container or
    output template are different downloads, and naming the wrong one tells the user their file is
    something it is not.
    """
    preset = presets.by_name("Audio only (original)")
    request = presets.to_request(preset, url="https://example.invalid/clip", output_directory="/d")
    job = Job(
        id="job-1",
        url=request.url,
        request=request,
        status=JobStatus.QUEUED,
        queue_position=0,
    )
    window = _window_over([job], tmp_path)
    view = window.queue_view
    assert view is not None

    assert view.model.data(view.model.index(0, 0), PRESET_ROLE) == "Audio only (original)"


def test_a_custom_selector_claims_to_be_no_preset(qapp: QApplication, tmp_path: Path) -> None:
    """`REQ-009`'s escape hatch. A request no built-in describes must not borrow a name.

    The row still says what it is in words on its last line; what it must not do is report itself
    as one of the choices, because then the control would show a format the job is not using.
    """
    window = _window_over([_job("job-1", 0, JobStatus.QUEUED)], tmp_path)
    view = window.queue_view
    assert view is not None

    # `_job`'s request is a bare `best` selector with a default template — deliberately not any
    # built-in preset.
    assert view.model.data(view.model.index(0, 0), PRESET_ROLE) is None, (
        "a request no built-in describes reported itself as a preset, so the control would show "
        "a format this download is not using"
    )


# --- DAT-005 / T-125: the confirmation, and the promise it carries ---------------------------


class _MutableQueue:
    """A `QueueReader` whose set of jobs can change, so a reset can be provoked.

    `_FakeQueue` above is deliberately fixed: every test before this one is about one arrangement.
    The `T126-R1` and `T124-R2` regressions are about what happens **when the arrangement
    changes**, which a fixed reader cannot express — and the reviewer's probe found exactly the
    defects that only appear on that path.
    """

    def __init__(self, jobs: list[Job]) -> None:
        self.jobs = list(jobs)

    def get(self, job_id: str) -> Job | None:
        return next((job for job in self.jobs if job.id == job_id), None)

    def all_jobs(self) -> list[Job]:
        return list(self.jobs)

    def swap_positions(self) -> None:
        """Exchange the two jobs' `queue_position`, which is what a reorder actually writes.

        Reversing the list would prove nothing: `QueueModel` sorts by `queue_position` and not by
        the reader's order, so a fake that only reversed itself would leave the table looking
        exactly as it did and the identity claim below would pass without a reorder happening.
        """
        first, second = self.jobs[0], self.jobs[1]
        self.jobs = [
            replace(first, queue_position=second.queue_position),
            replace(second, queue_position=first.queue_position),
        ]


def _shown_window(queue: _MutableQueue, tmp_path: Path, **handlers: Any) -> MainWindow:
    """A real window, **shown**, over a reader whose contents can change.

    Shown matters and is not ceremony: an unshown view lays nothing out, opens no editor and
    delivers no key events, so every route this section is about is unobservable without it —
    which is precisely why the committed tests called `_show_row_menu()` and `model.setData()`
    directly and could not see that neither had a user route into it (`T124-R1`, `T126-R1`).
    """
    manager = DownloadManager(_EmptyJobStore(), concurrency=1)  # type: ignore[arg-type]
    manager.start_queue()
    window = MainWindow(
        geometry_file=tmp_path / "window.toml",
        concurrency=1,
        control_bar=True,
        manager=manager,
        queue=queue,
        **handlers,
    )
    window.show()
    QApplication.processEvents()
    return window


def _open_the_format_editor(view: Any, job_id: str) -> QComboBox:
    """Open a row's format control the way `EDIT_KEY` does, and return the live editor."""
    row = view.model.row_of(job_id)
    assert row is not None, f"{job_id} is not in the queue"
    index = view.model.index(row, 0)
    view.table.setCurrentIndex(index)
    view.table.edit(index)
    QApplication.processEvents()
    editor = view.table.findChild(QComboBox, ROW_PRESET_NAME)
    assert isinstance(editor, QComboBox), "no editor opened on the row"
    return editor


@pytest.mark.parametrize("disturbance", ["reorder", "remove"])
def test_a_format_chosen_survives_the_queue_changing_underneath_it(
    qapp: QApplication, tmp_path: Path, disturbance: str
) -> None:
    """**`T126-R1`, the Critical.** A structural reset must not swallow an open choice.

    `QueueModel.refresh()` fully resets on remove, reorder and clear. Qt invalidates a live
    editor's index on reset and then disowns the widget, so a commit attempted afterwards is
    refused: `setData` is never reached and the visible choice is discarded **in silence** while
    the download goes on running as whatever it was. The add dialog was given this lifecycle by
    `T118-R14`; the queue was given the same delegate without it.

    The reviewer's probe is reproduced here: choose MP3 for job B in a **shown** view, then let
    the queue change under it. The committed coverage called `model.setData()` directly and so
    could never see this route at all.

    **Asserted through the durable request**, not through the signal: `retarget` is what the
    worker would read, and a `preset_chosen` that reached nothing would satisfy a weaker test.

    Mutation: deleting the `modelAboutToBeReset` → `_commit_open_editor` connection fails both
    parametrizations, and committing *after* the reset instead of before fails them too — Qt
    warns and `retarget` is never asked.
    """
    queue = _MutableQueue([_job("job-a", 0), _job("job-b", 1)])
    window = _shown_window(queue, tmp_path)
    view = window.queue_view
    assert view is not None
    asked: list[tuple[str, str]] = []
    assert window._manager is not None
    window._manager.retarget = (  # type: ignore[method-assign]
        lambda job_id, request, **_: asked.append((job_id, request.format_selector))
    )

    editor = _open_the_format_editor(view, "job-b")
    editor.setCurrentIndex(editor.findData("Audio only (MP3)"))

    if disturbance == "reorder":
        queue.swap_positions()
        window._manager.queue_reordered.emit(["job-b", "job-a"])
    else:
        queue.jobs = [job for job in queue.jobs if job.id != "job-a"]
        window._manager.job_removed.emit("job-a")
    QApplication.processEvents()

    assert asked == [("job-b", presets.by_name("Audio only (MP3)").format_selector)], (
        f"a {disturbance} produced {asked}. The user chose MP3 for job-b and the queue changed "
        "underneath the open control; the choice must reach retarget for the job it was made "
        "for, or the download runs as the format the user replaced"
    )


def test_the_editor_comes_back_on_the_same_job_after_a_reorder(
    qapp: QApplication, tmp_path: Path
) -> None:
    """The other half of `T126-R1`: restored **by identity**, not by row number.

    A reorder is one of the three things that resets the model, so the row number the editor had
    is precisely what cannot be trusted afterwards. Reopening on the old number would put the
    control back on whichever job now occupies it — which is `T118-R14`'s defect exactly, moved
    one surface over.
    """
    queue = _MutableQueue([_job("job-a", 0), _job("job-b", 1)])
    window = _shown_window(queue, tmp_path)
    view = window.queue_view
    assert view is not None

    _open_the_format_editor(view, "job-b")
    assert view.model.row_of("job-b") == 1
    manager = window._manager
    assert manager is not None

    queue.swap_positions()
    manager.queue_reordered.emit(["job-b", "job-a"])
    QApplication.processEvents()

    assert view.model.row_of("job-b") == 0, "the fake did not actually reorder"
    assert view.table.currentIndex().row() == 0, (
        "the editor was restored onto row 1, which is now job-a — an index that outlived the row "
        "it named, which is the whole of T118-R14"
    )
    assert view.table.findChild(QComboBox, ROW_PRESET_NAME) is not None, (
        "no editor came back at all, so a reorder elsewhere in the queue closes the control the "
        "user is in the middle of using"
    )


def test_a_fast_retarget_does_not_turn_the_success_refresh_into_a_loop(
    qapp: QApplication, tmp_path: Path
) -> None:
    """Reviewer regression: reopening must not report the redisplayed value as a new choice.

    If the retarget write settles before the reorder refresh rereads the queue, the restored
    editor already shows the newly durable preset.  The success callback then refreshes once
    more.  Committing the restored editor during that refresh emits the same choice again;
    DownloadManager's ``UNCHANGED`` path invokes the success callback synchronously, producing
    an unbounded refresh/retarget recursion.  Updating the backing reader in the fake is what the
    submitted list-append fake omitted and what makes this ordering observable.
    """
    queue = _MutableQueue([_job("job-a", 0), _job("job-b", 1)])
    window = _shown_window(queue, tmp_path)
    view = window.queue_view
    assert view is not None
    manager = window._manager
    assert manager is not None
    asked: list[tuple[str, str]] = []
    settled: list[Any] = []

    def retarget(job_id: str, request: DownloadRequest, **callbacks: Any) -> None:
        asked.append((job_id, request.format_selector))
        queue.jobs = [
            replace(job, request=request) if job.id == job_id else job for job in queue.jobs
        ]
        then = callbacks.get("then")
        if len(asked) == 1 and callable(then):
            settled.append(then)

    manager.retarget = retarget  # type: ignore[method-assign]
    editor = _open_the_format_editor(view, "job-b")
    editor.setCurrentIndex(editor.findData("Audio only (MP3)"))

    queue.swap_positions()
    manager.queue_reordered.emit(["job-b", "job-a"])
    QApplication.processEvents()
    assert len(settled) == 1, "the first retarget did not expose its success refresh"
    settled.pop()()
    QApplication.processEvents()

    assert asked == [("job-b", presets.by_name("Audio only (MP3)").format_selector)], (
        f"redisplaying the durable choice reported it as another user choice: {asked}"
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (JobStatus.QUEUED, ""),
        (JobStatus.READY, ""),
        (JobStatus.RUNNING, "Download as: Best video available"),
        (JobStatus.POST_PROCESSING, "Download as: Best video available"),
        (JobStatus.COMPLETED, "Download as: Best video available"),
        (JobStatus.FAILED, "Download as: Best video available"),
    ],
)
def test_a_row_says_its_format_once_the_control_is_gone(
    qapp: QApplication, tmp_path: Path, status: JobStatus, expected: str
) -> None:
    """`UX-005` §6 has two halves and only the first was built (`T126-R2`).

    *"A control on queued and waiting rows, plain text once a download starts."* The control
    disappeared when the job left `RETARGETABLE` and **nothing replaced it**, so a running
    download said nothing anywhere about what format it was running as — on the one surface
    `UX-005` removed the detail pane from.

    Read from the durable request, which is what the worker was handed: a rendering derived from
    anything else is a second opinion about the download in flight.
    """
    preset = presets.by_name("Best video available")
    request = presets.to_request(preset, url="https://example.invalid/clip", output_directory="/d")
    job = Job(id="job-1", url=request.url, request=request, status=status, queue_position=0)
    window = _window_over([job], tmp_path)
    view = window.queue_view
    assert view is not None

    drawn = view.model.data(view.model.index(0, 0), SELECTOR_ROLE)

    assert drawn == expected, (
        f"a {status.value} row draws {drawn!r} where UX-005 §6 wants {expected!r} — the control "
        "and the text are the two halves of one rule, and exactly one of them belongs on any row"
    )


def test_a_custom_selector_is_spelled_out_rather_than_left_blank(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`REQ-009` allows a selector no built-in describes, and the row must still say what it is.

    Deriving the text from the preset list alone leaves this row silent — the case
    `_preset_name_for` answers `None` for — which is the same "says nothing about its format"
    defect `T126-R2` found, surviving in the shape a name-only fix would leave behind.
    """
    request = DownloadRequest(
        url="https://example.invalid/clip",
        output_directory="/downloads",
        format_selector="bestvideo[height<=720]+bestaudio",
        output_template="%(title)s.%(ext)s",
    )
    job = Job(
        id="job-1",
        url=request.url,
        request=request,
        status=JobStatus.RUNNING,
        queue_position=0,
    )
    window = _window_over([job], tmp_path)
    view = window.queue_view
    assert view is not None

    assert view.model.data(view.model.index(0, 0), SELECTOR_ROLE) == (
        "Download as: bestvideo[height<=720]+bestaudio"
    ), "a custom selector left the row with nothing to say about its own format"


def _bring_to_front(window: MainWindow, view: Any) -> None:
    """Let `view` lay out, so its rows have real rectangles.

    *(This selected `view`'s tab. `T-169` left one surface, so the window's central widget **is**
    the view and there is nothing to bring forward — what the helper still buys is the event turn
    that makes the list lay out, which every caller here depends on.)*
    """
    assert window.centralWidget() is view, "the window's central widget is not this view"
    QApplication.processEvents()


def _press_the_menu_key(table: Any) -> None:
    """Deliver what the Menu key delivers: a keyboard-reason context-menu event, off any row.

    **`QTest.keyClick(Key_Menu)` cannot be used, and that was measured rather than assumed.** The
    Menu-key and Shift+F10 translation into `QEvent::ContextMenu` is done by the platform plugin,
    not by `QWidget`, so under `offscreen` — which is every Qt test this project runs (`NFR-005`,
    `docs/project/TESTING.md`) — the key press arrives as a plain key press and no context menu is
    ever generated. Probed both ways before writing this: through the widget and through its window
    handle, with `contextMenuEvent` instrumented, and neither produced one.

    So this sends the object the platform sends. Everything under test is still exercised: Qt's
    own `CustomContextMenu` dispatch, the emitted `customContextMenuRequested`, the handler, and
    the shell that builds the menu. What is *not* covered is the plugin's own translation, which
    is Qt's and which `contextMenuPolicy` is asserted for separately below.

    **The position is deliberately off every row**, which is the keyboard case: a position derived
    from the widget rather than from a row is what made `indexAt` answer "no row" for every
    keyboard request, and a handler that only resolves through `indexAt` fails here and passes a
    mouse-shaped test.
    """
    viewport = table.viewport()
    model = table.model()
    last = table.visualRect(model.index(model.rowCount() - 1, 0))
    off_any_row = QPoint(1, max(last.bottom() + 2, viewport.height() + 2))
    assert not table.indexAt(off_any_row).isValid(), (
        "the probe position landed on a row, so this asserts the mouse route rather than the "
        "keyboard one"
    )
    QApplication.sendEvent(
        viewport,
        QContextMenuEvent(
            QContextMenuEvent.Reason.Keyboard, off_any_row, viewport.mapToGlobal(off_any_row)
        ),
    )
    QApplication.processEvents()


def test_the_menu_key_raises_the_rows_overflow(qapp: QApplication, tmp_path: Path) -> None:
    """`UX-005` §4 declares `⋯` the keyboard route, and the list did not have one (`T124-R1`).

    *(This ran for both lists until `T-169` left one. What it asserts about the queue's row is
    unchanged.)*

    `RowDelegate.editorEvent` answers **left-button mouse events only**, and nothing installed a
    keyboard or context-menu route on either view — so the declared no-pointer route did not
    exist, and the committed tests called `_show_row_menu()` directly and could not tell.

    Driven on a **shown** view, from the focused row, through the event the Menu key produces —
    see `_press_the_menu_key` for why the literal key press cannot be sent under `offscreen`.
    """
    queue = _MutableQueue([_job("job-1", 0, JobStatus.FAILED)])
    window = _shown_window(queue, tmp_path, retry=lambda _: None)
    view = window.queue_view
    assert view is not None
    row_id = "job-1"
    _bring_to_front(window, view)
    assert view.select(row_id)
    view.table.setFocus()

    assert view.table.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu, (
        "without this policy the platform routes the Menu key to a default menu instead of to "
        "this application, and the row's verbs stay pointer-only"
    )
    _press_the_menu_key(view.table)

    menu = next(
        (child for child in window.findChildren(QMenu) if child.objectName() == "rowVerbsMenu"),
        None,
    )
    assert menu is not None, (
        "the Menu key on the queue list raised no overflow menu, so every verb the row could "
        "not fit is unreachable without a pointer"
    )
    try:
        assert [action.text() for action in menu.actions()] == [
            LABELS[verb] for verb in view.verbs_of(row_id)
        ], "the menu the keyboard raised does not hold what the row offers"
    finally:
        menu.close()


def test_a_queue_row_draws_the_uploader_and_the_duration(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`UX-005` §3's row anatomy, on the tab the user watches (`T124-R4`).

    Read through `DETAIL_ROLE` — the role the delegate actually paints — rather than off the job,
    which would assert that a field this test set is the field this test set. Both are absent from
    `REQ-014`'s columns on purpose: they are what identifies the thing rather than its progress,
    so they lead the line and the columns follow.
    """
    job = replace(
        _job("job-1", 0, JobStatus.RUNNING),
        uploader="Someone Who Publishes",
        duration_seconds=212.5,
    )
    window = _window_over([job], tmp_path)
    view = window.queue_view
    assert view is not None

    detail = view.model.data(view.model.index(0, 0), DETAIL_ROLE)

    assert detail.startswith("Someone Who Publishes · 3:32"), (
        f"the row's second line reads {detail!r}; UX-005 §3 names uploader and duration, and a "
        "queue that shows neither is the accepted anatomy holding only until Add is pressed"
    )


def test_a_row_the_probe_learned_nothing_about_draws_no_empty_fields(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`None` is not a value to render (`T124-R4`).

    An unprobed row must not gain a stray separator or an em dash where the uploader would be —
    `format_duration` renders `None` as `UNKNOWN_TEXT` for the add dialog's own layout, and that
    placeholder between a title and a percentage says less than nothing.
    """
    window = _window_over([_job("job-1", 0, JobStatus.RUNNING)], tmp_path)
    view = window.queue_view
    assert view is not None

    detail = view.model.data(view.model.index(0, 0), DETAIL_ROLE)

    assert detail.split(" · ")[0] == view.model.text_at("job-1", PROGRESS_COLUMN), (
        f"the row's second line reads {detail!r}; with neither field learned it must open on the "
        f"progress, not on a placeholder or on the gap two absent fields left. "
        f"({UNKNOWN_TEXT!r} is what format_duration renders None as, and it belongs in the add "
        "dialog's fixed layout rather than in this joined line.)"
    )


def test_a_screen_reader_hears_every_field_the_row_draws(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`NFR-005`: the drawn row and the spoken row are one set of fields (`T124-R4`, `T126-R2`).

    `_whole_row` was built from `COLUMN_HEADERS` alone, which is `REQ-014`'s six. The row draws two
    things that are not among them — the uploader and duration `UX-005` §3 names, and the format
    text a started download shows since `T126-R2` — so a sighted user and a screen-reader user were
    being told different things about one download. That is `T017-R2`, which this project has
    already paid for once.

    Each is **named**, not read as a bare value, for the reason `_accessible_text` gives about
    `47%`: a number with no field name says nothing about which field is being heard.
    """
    preset = presets.by_name("Best video available")
    request = presets.to_request(preset, url="https://example.invalid/clip", output_directory="/d")
    job = Job(
        id="job-1",
        url=request.url,
        request=request,
        status=JobStatus.RUNNING,
        queue_position=0,
        uploader="Someone Who Publishes",
        duration_seconds=212.5,
    )
    window = _window_over([job], tmp_path)
    view = window.queue_view
    assert view is not None

    spoken = view.model.data(view.model.index(0, 0), Qt.ItemDataRole.AccessibleTextRole)

    for field in ("Uploader: Someone Who Publishes", "Duration: 3:32", "Download as: Best video"):
        assert field in spoken, (
            f"the row draws {field!r} and a screen reader hears {spoken!r} — one download, two "
            "descriptions, which is T017-R2"
        )


def test_a_screen_reader_is_told_nothing_the_row_does_not_draw(
    qapp: QApplication, tmp_path: Path
) -> None:
    """The mirror, and it is the half a placeholder would pass.

    An unprobed row draws no uploader and no duration; speaking `Uploader:` with nothing after it
    would be describing a row that is not there.

    **And no format line while the control can name the format.** The row's request here is a
    built-in, so the control reads "Best video available" and the line would be the same fact
    twice, in two places that can disagree.

    *(This used `_job()`'s own request, whose `format_selector="best"` matches no built-in — so
    after `T126-R4` that row is a custom-selector row and correctly *does* speak its format. The
    test's premise was "retargetable means silent", which was true until the control stopped being
    able to say it for every row. The condition is now status **and** whether a built-in describes
    the request, and this case is the one where both hold.)*
    """
    preset = presets.by_name("Best video available")
    request = presets.to_request(preset, url="https://example.invalid/clip", output_directory="/d")
    job = Job(
        id="job-1", url=request.url, request=request, status=JobStatus.QUEUED, queue_position=0
    )
    window = _window_over([job], tmp_path)
    view = window.queue_view
    assert view is not None

    spoken = view.model.data(view.model.index(0, 0), Qt.ItemDataRole.AccessibleTextRole)

    for absent in ("Uploader:", "Duration:", FORMAT_PREFIX):
        assert absent not in spoken, (
            f"a screen reader hears {absent!r} on a row that draws no such field: {spoken!r}"
        )


def test_a_queue_row_with_a_custom_selector_says_so_while_it_is_still_editable(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`T126-R4`'s other half: dropping the inherited entry must not make a row silent.

    The control offers built-ins, so a request no built-in describes leaves it showing nothing.
    Before `T126-R4` that row read **Same as all** — naming a batch the queue does not have — and
    simply deleting the entry would have replaced a false statement with no statement, which is
    `T126-R2`'s defect arriving from the other side. So the row's own line speaks exactly when the
    control cannot, and a screen reader hears it for the same reason.
    """
    request = DownloadRequest(
        url="https://example.invalid/clip",
        output_directory="/downloads",
        format_selector="bestvideo[height<=720]+bestaudio",
        output_template="%(title)s.%(ext)s",
    )
    job = Job(
        id="job-1", url=request.url, request=request, status=JobStatus.QUEUED, queue_position=0
    )
    window = _window_over([job], tmp_path)
    view = window.queue_view
    assert view is not None
    cell = view.model.index(0, 0)

    assert view.model.data(cell, PRESET_CHOICES_ROLE), (
        "a queued row must still offer the control; this test is about what it says beside it"
    )
    assert view.model.data(cell, SELECTOR_ROLE) == (
        "Download as: bestvideo[height<=720]+bestaudio"
    ), "a retargetable row whose format the control cannot name said nothing about it"
    assert FORMAT_PREFIX in view.model.data(cell, Qt.ItemDataRole.AccessibleTextRole), (
        "the line is drawn and not spoken, which is the T017-R2 split"
    )


class _WritableStore:
    """A `JobStore` **and** a `QueueReader` over one dictionary (`T126-R3`).

    `_EmptyJobStore` answers `None` to everything, and `_MutableQueue` is read-only — so neither
    can carry a *real* `DownloadManager.retarget` through to its `UNCHANGED` branch, which is the
    engine of the loop `T126-R3` found. This one applies the write and answers `get` from the same
    dictionary, which is exactly the obligation `JobStore` documents: *`get` reflects a queued
    `update` immediately*.

    `update` calls back synchronously. The real `PersistentJobStore` does not, and that difference
    is stated rather than glossed: it means this fake reaches `_settle` on the same stack, which is
    the shape the `UNCHANGED` branch already has unconditionally — that branch calls `then()`
    inline whether or not any store is involved, and it is the branch `T126-R3` turns on.
    """

    def __init__(self, jobs: list[Job]) -> None:
        self.jobs: dict[str, Job] = {job.id: job for job in jobs}

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def all_jobs(self) -> list[Job]:
        return list(self.jobs.values())

    def update(self, job: Job, done: Callable[[str | None], None]) -> None:
        self.jobs[job.id] = job
        done(None)

    def requeue_at_end(self, job: Job, done: Any) -> None:
        self.update(job, done)

    def remove(self, job_id: str, done: Callable[[str | None], None]) -> None:
        self.jobs.pop(job_id, None)
        done(None)

    def reorder(self, job_ids: Any, done: Callable[[str | None], None]) -> None:
        done(None)

    def clear_completed(self, done: Callable[[str | None], None]) -> None:
        done(None)


def test_a_lifecycle_commit_of_an_unchanged_editor_never_reaches_the_manager(
    qapp: QApplication, tmp_path: Path
) -> None:
    """**`T126-R3`, with the real manager and its real `UNCHANGED` branch.**

    The reviewer's regression above proves the ordering with `retarget` replaced by a recorder.
    This one leaves `DownloadManager.retarget` in place over a store that really writes, so the
    engine that makes the loop unbounded actually runs: `_persist` computes the revision, finds
    the durable request already equal to the one asked for, answers `UNCHANGED`, and calls `then`
    — `refresh_queue` — **inline, on the same stack**, with no store and no event loop between.

    **The state is arranged, not stumbled into.** `job-b`'s durable request is already MP3 before
    the editor opens, so `setEditorData` fills the control with the value the request already
    holds. That is precisely what a reopened editor holds after a retarget lands, and arranging it
    directly makes the claim deterministic instead of dependent on how two writes interleave.

    Then the queue changes underneath the open control, which commits it. The assertion is that
    **the manager is never asked at all**: a lifecycle commit of a value nothing chose is not a
    user edit, and every hop of the loop began with one that was allowed through. `retarget` is
    wrapped rather than replaced, so the real call still happens when it should.

    **`sys.setrecursionlimit` is lowered** so that if the loop ever returns, this fails in a few
    hundred frames rather than spending the default thousand inside a Qt slot. Restored in a
    `finally`, whatever happened.
    """
    mp3 = presets.by_name("Audio only (MP3)")
    already = presets.to_request(mp3, url="https://example.invalid/clip", output_directory="/d")
    store = _WritableStore(
        [_job("job-a", 0), replace(_job("job-b", 1), request=already, url=already.url)]
    )
    manager = DownloadManager(store, concurrency=1)
    manager.start_queue()
    window = MainWindow(
        geometry_file=tmp_path / "window.toml",
        concurrency=1,
        control_bar=True,
        manager=manager,
        queue=store,
    )
    window.show()
    QApplication.processEvents()
    view = window.queue_view
    assert view is not None

    asked: list[str] = []
    real = manager.retarget

    def watched(job_id: str, request: DownloadRequest, **callbacks: Any) -> None:
        asked.append(job_id)
        real(job_id, request, **callbacks)

    manager.retarget = watched  # type: ignore[method-assign]

    editor = _open_the_format_editor(view, "job-b")
    assert editor.currentData() == mp3.name, (
        f"the editor opened on {editor.currentData()!r}; this test needs it showing the value the "
        "request already holds, which is what a reopened editor shows after a retarget lands"
    )

    previous = sys.getrecursionlimit()
    sys.setrecursionlimit(300)
    try:
        store.jobs = {
            job_id: replace(job, queue_position=1 - (job.queue_position or 0))
            for job_id, job in store.jobs.items()
        }
        manager.queue_reordered.emit(["job-b", "job-a"])
        QApplication.processEvents()
    finally:
        sys.setrecursionlimit(previous)

    assert asked == [], (
        f"a lifecycle commit reported the redisplayed value as a user choice and reached the "
        f"manager {len(asked)} time(s): {asked}. retarget() answers UNCHANGED and calls its "
        "success refresh inline, so each one of these is a hop of an unbounded loop"
    )
    assert store.jobs["job-b"].request == already, "the durable request was rewritten by a no-op"
    assert view.model.data(view.model.index(view.model.row_of("job-b") or 0, 0), PRESET_ROLE) == (
        mp3.name
    ), "the row stopped showing the format that is durable"


def test_a_real_choice_still_reaches_the_durable_request_through_the_manager(
    qapp: QApplication, tmp_path: Path
) -> None:
    """The guard above must not cost the thing `T126-R1` exists to deliver.

    A refusal keyed on "the request already says this" is one comparison away from refusing
    everything, and a test that only asserts nothing happened would not notice. So: a genuine
    change, through the real `DownloadManager.retarget` and a store that really writes, with the
    queue reordering underneath the open control — the `T126-R1` case, end to end.
    """
    store = _WritableStore([_job("job-a", 0), _job("job-b", 1)])
    manager = DownloadManager(store, concurrency=1)
    manager.start_queue()
    window = MainWindow(
        geometry_file=tmp_path / "window.toml",
        concurrency=1,
        control_bar=True,
        manager=manager,
        queue=store,
    )
    window.show()
    QApplication.processEvents()
    view = window.queue_view
    assert view is not None

    editor = _open_the_format_editor(view, "job-b")
    editor.setCurrentIndex(editor.findData("Audio only (MP3)"))

    store.jobs = {
        job_id: replace(job, queue_position=1 - (job.queue_position or 0))
        for job_id, job in store.jobs.items()
    }
    manager.queue_reordered.emit(["job-b", "job-a"])
    QApplication.processEvents()

    wanted = presets.by_name("Audio only (MP3)")
    assert store.jobs["job-b"].request.format_selector == wanted.format_selector, (
        "the user's choice did not reach the durable request through the real manager"
    )
    assert store.jobs["job-a"].request.format_selector == "best", (
        "the choice made on job-b was written to job-a; the editor's index outlived its row"
    )


def test_a_queue_editor_does_not_offer_an_inapplicable_group_default(
    qapp: QApplication, tmp_path: Path
) -> None:
    """Reviewer regression: a durable queue row has no “all” whose format it can inherit.

    ``RowDelegate`` is shared with the staging dialog, where the first entry really does mean
    “use the format selected for the whole paste.”  The queue has only each job's durable request;
    it neither stores nor exposes that former group choice.  Nevertheless the shared editor adds
    ``Same as all`` unconditionally, and QueueModel rejects its ``None`` value.  That leaves a
    visible choice which silently does nothing, contrary to UX-005 section 5.
    """
    window = _shown_window(_MutableQueue([_job("job-1", 0)]), tmp_path)
    view = window.queue_view
    assert view is not None

    editor = _open_the_format_editor(view, "job-1")

    # **By the suffix, not by a fixed string** (`T-284`). The entry now reads the batch preset's
    # name followed by the relation, so an assertion against one spelling would pass the moment the
    # wording moved. Every entry the queue offers must be a preset, and no preset says this.
    offered = [editor.itemText(position) for position in range(editor.count())]
    assert not [text for text in offered if INHERITED_SUFFIX in text], (
        f"the queue offers an inherited entry — {offered} — but it has no group default to "
        "restore and its model refuses the entry's value"
    )
    assert all(editor.itemData(position) is not None for position in range(editor.count())), (
        "the queue offers an entry whose data is None, which is what *follow the batch* means and "
        "which QueueModel.setData refuses"
    )


# --- T-130: the mockup divergences the maintainer adopted --------------------------------------


def test_add_urls_is_the_first_thing_on_the_toolbar(qapp: QApplication, tmp_path: Path) -> None:
    """`UX-005`'s 2026-08-04 amendment, row 1 (`T-130`).

    The B1-b mockup opens the toolbar with `+ Add URLs` as the primary action. The shipped window
    had it under File and nowhere else — so the one thing this application exists to do was the one
    thing not on its toolbar.

    **Asserted as the first action**, not merely as present: the ruling is about primacy, and an
    Add button appended after *Clear finished* would satisfy "it is on the toolbar" while missing
    what the mockup was showing.
    """
    from PySide6.QtWidgets import QToolBar, QToolButton

    window = _window_over([_job("job-1", 0)], tmp_path)
    bar = window.findChild(QToolBar, "queueToolBar")
    assert bar is not None

    named = [action.objectName() for action in bar.actions() if action.objectName()]
    assert named and named[0] == "actionAddUrls", (
        f"the toolbar starts with {named[:1]}; UX-005's amendment puts the primary action first"
    )
    # **Read what the toolbar renders, not `QAction.text()`** (`T130-R2`, amended 2026-08-04 on
    # the maintainer's instruction). `QToolButton` draws `iconText()` in preference to `text()`,
    # which is how one `QAction` reads *"+ Add URLs"* here and *"Add URLs..."* in the File menu —
    # `T-016` chose that suffix for the Windows "opens a dialog" convention, and the amendment
    # adopted a *toolbar* button rather than a menu label. `text()` is a proxy for what the user
    # sees; the rendered label and the accessible name are the thing itself, and both read
    # "+ Add URLs" (measured).
    button = bar.widgetForAction(bar.actions()[0])
    # `widgetForAction` is typed as `QWidget`; a toolbar renders an action as a `QToolButton`, and
    # narrowing here is what lets the label be read rather than assumed.
    assert isinstance(button, QToolButton)
    visible = button.text().replace("&", "")
    assert visible.startswith("+ Add URLs"), (
        f"the primary toolbar button reads {visible!r}; the adopted mock and UX-005 amendment "
        "name it '+ Add URLs', not merely an Add action in the first slot"
    )
    announced = QAccessible.queryAccessibleInterface(button)
    assert announced.text(QAccessible.Text.Name).startswith("+ Add URLs"), (
        "the button is announced as something other than what it draws, which is the split "
        "`NFR-005` exists to prevent"
    )
    assert window.add_urls_action is not None


def test_the_windows_real_add_button_is_filled_after_the_toolbar_builds_it(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`T-132`'s brand fill, measured on the window the product actually builds.

    The isolated style test sets ``primaryAction`` on a bare button of its own.  This one lets
    ``QToolBar`` create the button and composes a real ``MainWindow`` around it, so the fill is
    sampled from the route a user gets rather than from a stand-in.

    **It does not guard a repolish, and there is none to guard** (`T132-R2`).  `T132-R1` claimed
    the shipped button rendered neutral because a dynamic property set after the first polish is
    ignored; that finding was withdrawn as reviewer error, having measured a *disabled* action
    that `UX-005` row 6 says is correctly not filled.  What this test still earns its place for
    is the composition: it is the only assertion that the enabled primary action is brand-filled
    in a window built the way the application builds one.
    """
    previous_sheet = qapp.styleSheet()
    previous_palette = qapp.palette()
    window: MainWindow | None = None
    try:
        theme.apply(qapp, theme.LIGHT)
        # **Composed so `T-016` leaves the action enabled**, which needs a manager, a job sink and
        # an output directory (`MainWindow.can_add_urls`). `_window_over` supplies only the first,
        # so the action is disabled there and the sheet gives it `sunken` — correctly, because
        # `UX-005` row 6 adopted that a disabled primary is *not* filled.
        #
        # **Not `setEnabled(True)` on the button the toolbar built.** Forcing the state on a
        # widget from outside measures a widget nobody ships; composing the window so `T-016`
        # leaves the action enabled measures the real one. Measured either way: property `True`,
        # disabled `#EAEFE9`, enabled `#1E5E47` — and that gap is what `T132-R1` mistook for a
        # styling defect. Built directly rather than through `_window_over`, whose own first
        # parameter is called `jobs` and so cannot pass a job *sink* through to the window.
        window = MainWindow(
            geometry_file=tmp_path / "window.toml",
            concurrency=1,
            control_bar=True,
            manager=DownloadManager(_EmptyJobStore(), concurrency=1),  # type: ignore[arg-type]
            queue=_FakeQueue([_job("job-1", 0)]),
            jobs=_RecordingSink(),
            output_directory=tmp_path / "downloads",
        )
        window.resize(900, 620)
        window.show()
        qapp.processEvents()

        button = window.findChild(QToolButton, "addUrlsButton")
        assert button is not None
        assert button.isEnabled(), (
            "the composed window still disables Add URLs, so this measures the disabled fill"
        )

        image = button.grab().toImage()
        sampled = f"#{image.pixel(button.width() // 2, 4) & 0xFFFFFF:06X}"
        assert sampled == theme.LIGHT.primary.upper(), (
            f"the real Add URLs button fills with {sampled}, not the brand "
            f"{theme.LIGHT.primary}; the enabled primary action is not reading UX-005 row 6"
        )
    finally:
        if window is not None:
            window.close()
        qapp.setPalette(previous_palette)
        qapp.setStyleSheet(previous_sheet)


def test_the_toolbar_and_the_menu_share_one_add_action(qapp: QApplication, tmp_path: Path) -> None:
    """One `QAction`, two places it appears — not two actions (`T-130`).

    `T-016` disables this action, and explains why in a status tip, when composition supplied no
    manager. A second action would be a second place for that to keep being true, and the first
    time they differed a user would get a button that opens a dialog with nothing behind it.
    """
    window = _window_over([_job("job-1", 0)], tmp_path)
    from PySide6.QtGui import QAction

    menu_actions = [
        action for action in window.findChildren(QAction) if action.objectName() == "actionAddUrls"
    ]
    assert len(menu_actions) == 1, (
        f"{len(menu_actions)} Add URLs actions exist; the toolbar must show the menu's, not a copy"
    )
    assert window.add_urls_action is menu_actions[0]


def test_the_chip_takes_width_from_the_title_rather_than_overlapping_it(
    qapp: QApplication, tmp_path: Path
) -> None:
    """The chip shares the title's line, so the title must be elided to what is left.

    Drawn rather than reasoned about: a chip that overlapped the title would still satisfy any
    assertion about the role, and the row would be unreadable exactly where the name is.
    """
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QStyleOptionViewItem

    from tracks_and_trails.ui.row_delegate import RowDelegate

    window = _window_over([_job("job-1", 0)], tmp_path)
    view = window.queue_view
    assert view is not None
    model = view.model

    def paint(chip: bool) -> bytes:
        delegate = RowDelegate()
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, 420, 80)
        option.font = view.table.font()
        option.fontMetrics = QFontMetrics(option.font)
        image = QImage(420, 80, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        try:
            original = model.data

            def without_the_chip(index: Any, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
                """The same model with one role silenced, so only the chip differs."""
                return None if role == STATE_CHIP_ROLE else original(index, role)

            if not chip:
                model.data = without_the_chip  # type: ignore[method-assign]
            delegate.paint(painter, option, model.index(0, 0))
        finally:
            painter.end()
            model.data = original  # type: ignore[method-assign]
        return bytes(image.constBits())

    assert paint(chip=True) != paint(chip=False), (
        "the row draws identically with and without the chip, so the chip is not being drawn"
    )


# --- T-132, T-134, T-135: the second sitting at the window -----------------------------------


def test_the_queue_verbs_sit_at_the_far_end_of_the_toolbar(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`UX-005` row 7 (`T-132`): the mockup's `.spacer{flex:1 1 auto}`.

    What *adds* work and what *acts on work already queued* are different kinds of verb. Packed
    left, `Clear finished` ran straight up against the concurrency spinner that stood there then
    (`UX-013` has since moved it to the Settings screen).

    **Asserted by geometry, not by insertion order.** A separator inserted in the right place
    would satisfy an order check and still leave everything bunched at the left.

    **The free space is compared to itself rather than to a fraction of the bar**, which is what
    the spacer actually does: all of it collects *before* the group. The bound was
    `gap > bar.width() // 3`, calibrated when two verbs sat there; `T-144`'s `Clear history` made
    the group wider and drove the same correct layout to 294px against a 300px threshold — under
    the full suite only, where an earlier test's stylesheet widens the buttons. A threshold that
    moves when a button is added was measuring the group's width as much as its position.
    """
    window = _window_over([_job("job-1", 0)], tmp_path)
    window.resize(900, 500)
    window.show()
    qapp.processEvents()
    bar = window.findChild(QToolBar, "queueToolBar")
    assert bar is not None

    # **The left group's last widget is the anchor.** This measured from the concurrency spinner's
    # right edge until `UX-013` moved that spinner to the Settings screen (`T-234`); *Add URLs* is
    # what now sits at the left end, and the spacer's job — collect the free space *before* the
    # list verbs — is unchanged by which widget precedes it.
    adds = bar.findChild(QToolButton, "addUrlsButton")
    assert adds is not None
    list_verbs = [
        widget
        for action in bar.actions()
        if action.objectName() in {"runQueueAction", "clearCompletedAction"}
        and (widget := bar.widgetForAction(action)) is not None
    ]
    # Two, not three: `Clear history` left the toolbar with the list it emptied (`T-169`), and
    # the ledger that briefly replaced it — and its one Settings control — went the same day
    # (`REQ-020` withdrawn). Nothing is waiting to become a third (`T-176`).
    assert len(list_verbs) == 2, "the toolbar no longer holds both whole-list verbs"

    gap = min(widget.x() for widget in list_verbs) - (adds.x() + adds.width())
    trailing = bar.width() - max(widget.x() + widget.width() for widget in list_verbs)
    assert gap > trailing, (
        f"{gap}px of free space sits before the list verbs and {trailing}px after them on a "
        f"{bar.width()}px toolbar, so they are not at the far end"
    )


def test_the_verb_under_the_pointer_is_drawn_differently(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`T-134`: a painted button that never reacts is a picture of a control.

    `T118-R12` established that a reserved slot with nothing drawn in it is an affordance only for
    someone who already knows it is there. A button that looks pressable and answers nothing on
    contact is that defect one step later.

    Two paints of **the same row**, differing only in where the pointer is.
    """
    window = _window_over([_job("job-1", 0, JobStatus.QUEUED)], tmp_path)
    view = window.queue_view
    assert view is not None
    delegate = view.table.itemDelegate()
    assert isinstance(delegate, RowDelegate)
    index = view.model.index(0, 0)

    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 700, 90)
    option.font = view.table.font()
    option.fontMetrics = QFontMetrics(option.font)

    def painted() -> bytes:
        image = QImage(700, 90, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        try:
            delegate.paint(painter, option, index)
        finally:
            painter.end()
        return bytes(image.constBits())

    delegate.forget_hover()
    cold = painted()

    body, area = delegate._verb_area(option, index)
    rects = delegate._verb_rects(QFontMetrics(option.font), area, body, index)
    assert rects, "the row drew no verbs, so there is nothing to hover"
    delegate._hovered = (0, rects[0][0])
    warm = painted()

    assert cold != warm, (
        "the row drew identically with and without a verb under the pointer; the buttons do not "
        "acknowledge the pointer at all"
    )

    delegate.forget_hover()
    assert painted() == cold, (
        "clearing the hover did not restore the row, so the highlight outlives the pointer"
    )


def test_a_row_that_showed_every_verb_draws_no_overflow(qapp: QApplication, tmp_path: Path) -> None:
    """`UX-005` row 8 (`T-135`): the `⋯` is for what did not fit.

    It used to be drawn unconditionally and given the whole verb list, so a wide row offered the
    same three actions twice — once as buttons and once in a menu.

    Both directions in one test, because "no overflow" alone would pass if the overflow were
    removed outright and the menu with it.
    """
    window = _window_over([_job("job-1", 0, JobStatus.QUEUED)], tmp_path)
    view = window.queue_view
    assert view is not None
    delegate = view.table.itemDelegate()
    assert isinstance(delegate, RowDelegate)
    index = view.model.index(0, 0)
    metrics = QFontMetrics(view.table.font())
    body = QRect(0, 0, 900, 90).adjusted(PADDING, PADDING, -PADDING, -PADDING)

    roomy = QRect(body.left(), body.top(), 600, body.height())
    placed = delegate._verb_rects(metrics, roomy, body, index)
    offered = view.verbs_of("job-1")
    # `_verb_rects` answers rightmost-first, which is the order a hit test wants — so the row's
    # reading order is its reverse. Compared as a sequence rather than a set, because "the same
    # verbs in some order" would pass with the row drawing Cancel where Move up belongs.
    assert [verb for verb, _ in placed] == list(reversed(offered)), (
        f"a 600px row placed {[v for v, _ in placed]} for the {len(offered)} verbs it offers"
    )
    assert all(verb is not None for verb, _ in placed), (
        "a row with room for every verb still drew the overflow, so the menu behind it repeats "
        "buttons the user can already see"
    )

    cramped = QRect(body.left(), body.top(), 90, body.height())
    tight = delegate._verb_rects(metrics, cramped, body, index)
    assert any(verb is None for verb, _ in tight), (
        "a 90px row dropped verbs and drew no overflow, so they are unreachable by pointer"
    )


def test_the_overflow_menu_holds_what_the_row_dropped_and_not_what_it_showed(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`T-135`, through the record the paint actually wrote.

    The menu's contents come from what the last paint could not fit, so this paints a deliberately
    narrow row and then asks — the same order the user's click takes.
    """
    window = _window_over([_job("job-1", 0, JobStatus.QUEUED)], tmp_path)
    view = window.queue_view
    assert view is not None
    delegate = view.table.itemDelegate()
    assert isinstance(delegate, RowDelegate)
    index = view.model.index(0, 0)

    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 260, 90)
    option.font = view.table.font()
    option.fontMetrics = QFontMetrics(option.font)
    image = QImage(260, 90, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    try:
        delegate.paint(painter, option, index)
    finally:
        painter.end()

    dropped = delegate.overflowing("job-1")
    body, area = delegate._verb_area(option, index)
    drawn = {verb for verb, _ in delegate._verb_rects(QFontMetrics(option.font), area, body, index)}
    assert dropped, "a 260px row fitted every verb, so this measures nothing; narrow it further"
    assert not (set(dropped) & drawn), (
        f"the overflow offers {dropped} while the row is showing {drawn & set(dropped)}"
    )
    assert set(dropped) | (drawn - {None}) == set(view.verbs_of("job-1")), (
        "the drawn verbs and the overflow together are not what the row offers, so one of them is "
        "unreachable"
    )


def test_the_toolbars_verbs_are_drawn_as_buttons(qapp: QApplication, tmp_path: Path) -> None:
    """`T-132`, corrected twice — and **this test asserted the defect** in between.

    The first fault was that every tool button stamped a flat `window` fill over the toolbar's own
    vertical gradient, so the tint appeared to stop where the buttons began. I corrected it by
    making them **transparent**, and wrote a test asserting exactly that: *the toolbar's background
    runs behind its buttons*. It did. `Pause queue` and `Clear finished` became text on a toolbar —
    no border, no fill, nothing to press — and the maintainer reported them as no longer buttons.

    **The mockup says what they are**: `border: 1px solid var(--b); border-radius: 4px;
    background: var(--s)`. A deliberate shape does not have the original problem, because it is not
    pretending to be the bar.

    So the claim is inverted, and sampled **at the same `y`** — the toolbar's gradient means a
    pixel inside a button and one at a different height differ whatever the button looks like.
    """
    was_sheet, was_palette = qapp.styleSheet(), qapp.palette()
    try:
        theme.apply(qapp, theme.LIGHT)
        window = _window_over([_job("job-1", 0)], tmp_path)
        window.resize(900, 500)
        window.show()
        qapp.processEvents()
        bar = window.findChild(QToolBar, "queueToolBar")
        assert bar is not None
        verbs = [
            widget
            for action in bar.actions()
            if action.objectName() in {"runQueueAction", "clearCompletedAction"}
            and (widget := bar.widgetForAction(action)) is not None
        ]
        assert len(verbs) == 2, "the toolbar no longer holds both queue verbs"

        image = bar.grab().toImage()
        for button in verbs:
            # A toolbar renders an action as a `QToolButton`; narrowing is what lets the failure
            # message name the button rather than describe a `QWidget`.
            assert isinstance(button, QToolButton)
            box = button.geometry()
            row = box.top() + 2
            inside = image.pixel(box.center().x(), row)
            beside = image.pixel(bar.width() - 3, row)
            assert inside != beside, (
                f"{button.text()!r} is indistinguishable from the toolbar beside it at the same "
                "height, so it reads as text rather than as something to press"
            )
    finally:
        qapp.setStyleSheet(was_sheet)
        qapp.setPalette(was_palette)


def test_removing_a_playlist_asks_once_and_names_its_count(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`DAT-005` §4 at the group level (`T-140`, `T140-R5`).

    A bare *Remove* on a row that stands for sixteen files does not say how much is about to go,
    and a user who clicked the header meaning to click an entry has nothing to notice it by. One
    question carrying the count, then every member through the single removal implementation.
    """
    removed: list[str] = []
    window = _window_over([], tmp_path, on_remove_requested=removed.append)

    confirm = window._remove_group("pl-1", ["entry-0", "entry-1", "entry-2"])

    assert confirm is not None
    assert confirm.text() == "Remove these 3 downloads from the queue?", (
        f"the confirmation reads {confirm.text()!r}; DAT-005 section 4 makes it name its own count"
    )
    assert removed == [], "nothing may be removed before the user answers"

    confirm.buttonClicked.emit(confirm.button(QMessageBox.StandardButton.Yes))
    assert removed == ["entry-0", "entry-1", "entry-2"]
    confirm.close()


def test_a_single_member_group_removal_is_written_out_not_assembled(
    qapp: QApplication, tmp_path: Path
) -> None:
    """ "1 downloads" is the tell that a message was assembled rather than composed."""
    window = _window_over([], tmp_path, on_remove_requested=lambda _job_id: None)

    confirm = window._remove_group("pl-1", ["entry-0"])

    assert confirm is not None
    assert confirm.text() == "Remove this download from the queue?"
    confirm.close()


def test_declining_a_group_removal_removes_nothing(qapp: QApplication, tmp_path: Path) -> None:
    """The safe button is the default, so the accident this guards against is one keypress away."""
    removed: list[str] = []
    window = _window_over([], tmp_path, on_remove_requested=removed.append)

    confirm = window._remove_group("pl-1", ["entry-0", "entry-1"])
    assert confirm is not None
    assert confirm.defaultButton() == confirm.button(QMessageBox.StandardButton.No)

    confirm.buttonClicked.emit(confirm.button(QMessageBox.StandardButton.No))
    assert removed == []
    confirm.close()


def test_a_running_queue_looks_different_from_a_stopped_one(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`T-149`: pressing the run control must change something a person can see.

    **The state was always there and always invisible.** The control is one checkable `QAction` —
    Start and Stop are the same control — so Qt announced the toggled state to a screen reader
    and drew a checked tool button sunken, until `T-132`'s style sheet replaced its rendering
    without saying what checked means. `T-129` restored hover, pressed and disabled and missed
    this one, because this is the only checkable control on the toolbar.

    Rendered rather than asserted against the style sheet's text: a rule that exists and does not
    reach this button would pass a `grep` and fail a user, which is `T132-R1`'s whole lesson.

    **`T-181` made this harder to fail and the test is kept anyway.** The label now changes with
    the state too, so the rendering differs for a second reason. That is not a substitute: a label
    is the *name* of the verb and the checked state is the *state*, and `NFR-005` wants both.
    """
    previous_sheet = qapp.styleSheet()
    previous_palette = qapp.palette()
    window: MainWindow | None = None
    try:
        theme.apply(qapp, theme.LIGHT)
        window = _window_over([_job("job-1", 0, JobStatus.RUNNING)], tmp_path)
        window.resize(900, 620)
        window.show()
        qapp.processEvents()

        button = next(
            child
            for child in window.findChildren(QToolButton)
            if child.text().replace("&", "") == "Start"
        )
        stopped = button.grab().toImage()

        run = window.run_action
        assert run is not None
        run.setChecked(True)
        qapp.processEvents()
        running = button.grab().toImage()

        assert running != stopped, (
            "the toolbar draws a running queue exactly like a stopped one, so pressing Start "
            "changes nothing the user can see"
        )
    finally:
        if window is not None:
            window.close()
        qapp.setPalette(previous_palette)
        qapp.setStyleSheet(previous_sheet)


def test_the_keyboard_route_works_before_anything_has_been_clicked(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`T-152`: the declared keyboard route must not require a pointer first.

    `_row_menu_asked_for` resolves `indexAt(position)` and falls back to `currentIndex()` —
    `T124-R1`'s own fix, because Qt derives a keyboard request's position from the widget rather
    than from a row. It then returns when that index is invalid, and **nothing set one**, so the
    route did nothing until a click had selected a row. A keyboard route that needs a mouse is a
    mouse route with a shortcut (`NFR-005`).

    **This test deliberately never calls `setCurrentIndex`.** The existing coverage does, one line
    before pressing the key, which is why it proved the fallback works *given* a current row and
    could say nothing about a window where none was ever set — every window a user opens. That is
    the shape `T126-R3` and `T140-R1` are, at a third layer.
    """
    window = _window_over([_job("job-1", 0, JobStatus.RUNNING)], tmp_path)
    view = window.queue_view
    assert view is not None
    _bring_to_front(window, view)
    view.table.setFocus()

    assert view.table.currentIndex().isValid(), (
        "the list has rows and no current one, so the keyboard route has nothing to act on and "
        "returns silently"
    )

    _press_the_menu_key(view.table)

    menu = next(
        (child for child in window.findChildren(QMenu) if child.objectName() == "rowVerbsMenu"),
        None,
    )
    assert menu is not None, (
        "the Menu key raised nothing on a window where no row had been clicked, so the declared "
        "keyboard route is reachable only after using a pointer"
    )
    menu.close()
    window.close()


def test_the_rows_hold_the_keyboard_when_the_window_opens(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`T-152`, second round. **A current row was necessary and not sufficient.**

    `Shift+F10` is delivered to the *focused* widget, and nothing ever focused a view. Measured on
    a freshly opened window before the fix: `QSpinBox concurrencyChoice`, the toolbar's stepper. So
    the list's `customContextMenuRequested` could not fire however valid its current index was, and
    the maintainer saw no change from the first round.

    **This test calls no `setFocus`.** The round-one regression above does, one line before
    pressing the key — arranging the very condition the second defect is about, which is why the
    suite went on passing while the route stayed dead. Asserting the focused widget rather than
    synthesising the key is deliberate and disclosed: `offscreen` does not translate `Shift+F10`
    (`docs/project/TESTING.md`), so this proves the key would be **delivered to the list**, and the
    round-one test proves what the list does with it. Neither is an end-to-end proof and neither
    pretends to be.
    """
    window = _window_over([_job("job-1", 0, JobStatus.RUNNING)], tmp_path)
    window.show()
    QApplication.processEvents()
    view = window.queue_view
    assert view is not None

    focused = qapp.focusWidget()
    try:
        assert view.table.hasFocus(), (
            "the queue's rows do not hold the keyboard on a freshly opened window, so Shift+F10 "
            f"goes to {focused.objectName() if focused else None!r} instead and the row menu "
            "never opens"
        )
    finally:
        window.close()


def test_the_first_rows_of_a_first_run_take_the_keyboard(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`T-152`, second round, and the case construction alone cannot reach.

    An **empty** view hides its list, and a hidden widget cannot hold focus — so a first run has
    nothing to focus at construction and would start with the declared route dead until the user
    clicked something. That is the original defect, surviving in the one state a new user is
    guaranteed to be in.

    `modelReset` is the signal every structural change already goes through (`T080-R2`,
    `T124-R2`), so the keyboard is placed the moment there is somewhere to put it.
    """
    jobs: list[Job] = []
    manager = DownloadManager(_EmptyJobStore(), concurrency=1)  # type: ignore[arg-type]
    manager.start_queue()
    window = MainWindow(
        geometry_file=tmp_path / "window.toml",
        concurrency=1,
        control_bar=True,
        manager=manager,
        queue=_FakeQueue(jobs),
    )
    window.show()
    QApplication.processEvents()
    view = window.queue_view
    assert view is not None

    try:
        assert not view.table.hasFocus(), "the empty state must not focus its hidden list"

        jobs.append(_job("job-1", 0, JobStatus.RUNNING))
        window.refresh_queue()
        QApplication.processEvents()

        assert view.table.hasFocus(), (
            "the queue gained its first row and the keyboard stayed on the toolbar, so a first "
            "run reaches the row menu only after using a pointer — the defect this task is about"
        )
    finally:
        window.close()


def test_an_empty_queue_claims_no_keyboard_it_cannot_use(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`T-152`, second round, and `T-060`'s rule about focus chains.

    An empty view hides its list and answers an empty `focus_chain()`, so there is nothing to
    focus. Taking focus anyway would point the keyboard at a hidden widget and quietly swallow the
    key — worse than leaving it on a control the user can see.
    """
    window = _window_over([], tmp_path)
    window.show()
    QApplication.processEvents()
    view = window.queue_view
    assert view is not None

    try:
        assert view.shows_empty_notice, "this test needs the empty state to mean anything"
        assert not view.table.hasFocus(), (
            "the empty queue's hidden list took the keyboard, so every key goes to a widget "
            "nobody can see"
        )
    finally:
        window.close()


def test_the_keyboard_reaches_this_downloads_own_commands(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`T315-R1`: the item commands were reachable by pointer only, which `NFR-005` forbids.

    **The `⋮` that opens them is a painted affordance with no accessibility node** — deliberately,
    on the disclosure triangle's precedent, *because the same menu is reachable by right-click, the
    Menu key and Shift+F10*. `T-315` wired the zone to a new signal and left that second half
    unbuilt, so the justification for the painted-only control stopped being true. The reviewer
    measured it: a keyboard-reason context event on a selected queued row opened `↑ ↓ Cancel
    Remove` and neither new command.

    **The verbs are still there, below them.** The maintainer ruled the *pointer* menu holds the
    item commands alone, because the row draws its verbs as buttons a pointer user can see; a
    keyboard user has no such shortcut, so this route holds both. Asserted in that order, which is
    the staging list's own (`UX-011`).

    Driven on a **shown** view through the event the Menu key produces — see `_press_the_menu_key`
    for why the literal key press cannot be sent under `offscreen`.
    """
    queue = _MutableQueue([_job("job-1", 0, JobStatus.QUEUED)])
    window = _shown_window(queue, tmp_path)
    view = window.queue_view
    assert view is not None
    _bring_to_front(window, view)
    assert view.select("job-1")
    view.table.setFocus()

    _press_the_menu_key(view.table)

    menu = next(
        (child for child in window.findChildren(QMenu) if child.objectName() == "rowVerbsMenu"),
        None,
    )
    assert menu is not None, "the Menu key raised no menu at all"
    try:
        offered = [action.text() for action in menu.actions() if action.text()]
        assert CHOOSE_FORMATS_TEXT in offered, (
            f"the keyboard cannot reach the format table; the menu held {offered}"
        )
        assert OPTIONS_TEXT in offered, (
            f"the keyboard cannot reach this download's options; the menu held {offered}"
        )
        # The whole sequence, including the section heading, because *order* is the claim: the
        # item commands sit above the entries the menu already held (`UX-011`), and the verbs are
        # all still there — a route that gained the new commands by losing the old ones would
        # satisfy two `in` checks and be a regression.
        verbs = [LABELS[verb] for verb in view.verbs_of("job-1")]
        assert offered == [JUST_THIS_ITEM, CHOOSE_FORMATS_TEXT, OPTIONS_TEXT, *verbs], offered
    finally:
        menu.close()
