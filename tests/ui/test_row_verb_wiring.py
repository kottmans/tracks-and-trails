"""A row's verbs reach the same destinations the toolbar's do (`UX-005` §4, `T-124`).

`tests/ui/test_row_verbs.py` proves *which* verbs a state offers. This file proves that activating
one does something — and does the **same** thing the existing route does, rather than a second
implementation of it.

**Why that distinction is the whole file.** `T-016`'s record is an action that appeared to work
and quietly did nothing; `UX-005` §4 adds a second route to five effects that already had one, and
two routes to one effect is how one of them ends up with a guard the other lacks. So every test
below asserts the destination, not the signal.
"""

from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox

from tracks_and_trails.core import presets
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.core.models import DownloadRequest, Job
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.ui.main_window import (
    HISTORY_KEEPS_FILES,
    MainWindow,
    removal_question,
)
from tracks_and_trails.ui.row_delegate import (
    PADDING,
    PRESET_CHOICES_ROLE,
    PRESET_ROLE,
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


def _window_over(jobs: list[Job], tmp_path: Path, **handlers: Any) -> MainWindow:
    manager = DownloadManager(_EmptyJobStore(), concurrency=1)  # type: ignore[arg-type]
    return MainWindow(
        geometry_file=tmp_path / "window.toml",
        concurrency=1,
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
    """`UX-005` §4. The menu is the overflow, so it must not disagree with the row.

    Verbs are dropped from the row when they will not fit — `NFR-006` keeps the extractor's
    message at full width — and the menu is where they go. A menu built from its own table would
    be a second opinion about what a row offers, and the first time the two differed the user
    would be offered something the row had already decided against.
    """
    window = _window_over([_job("job-1", 0, JobStatus.FAILED)], tmp_path, retry=lambda _: None)
    menu = window._show_row_menu("job-1")
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
    menu = window._show_row_menu("job-1")
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
    assert window._show_row_menu("job-missing") is None


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
    """`UX-005` §4 accepts that the buttons shift; the **route** must not.

    `⋯` is the declared keyboard route, and a route that relocates as a download progresses is not
    a route. It is laid out first — rightmost — so every other verb moves around it.
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
    area = QRect(body.left() + 100, body.top(), body.width() - 100, body.height())

    places = []
    for row in (0, 1):
        placed = delegate._verb_rects(metrics, area, body, view.model.index(row, 0))
        overflow = next(rect for verb, rect in placed if verb is None)
        places.append(overflow)

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


def test_the_window_is_two_tabs_and_no_splitter(qapp: QApplication, tmp_path: Path) -> None:
    """`UX-005` §1: `Queue` and `History` are tabs, not panes in a splitter.

    **Asserted by there being no `QSplitter` anywhere in the window**, not merely by a tab widget
    existing. A tab widget added *beside* a surviving splitter would satisfy "there is a tab
    widget" and leave the layout the entry rejected — and the layout is what a user sees. The
    splitter is what `UX-005` was written to remove, so its absence is the claim.
    """
    from PySide6.QtWidgets import QSplitter, QTabWidget

    window = _window_over([_job("job-1", 0)], tmp_path)
    body = window.centralWidget()
    assert isinstance(body, QTabWidget), f"the window's body is a {type(body).__name__}"
    assert body.objectName() == "shellTabs"
    assert window.findChildren(QSplitter) == [], (
        "a QSplitter survives in the window; UX-005 replaced the splitter with tabs, and a tab "
        "widget added beside one leaves the layout the decision rejected"
    )


def test_each_tab_carries_its_count(qapp: QApplication, tmp_path: Path) -> None:
    """`UX-005` §1: a tab with a count is not a hiding place.

    This is the entire answer to the objection the splitter was built on — the source comment
    argued a tab would hide history. Asserted by **value**, so a label that stopped counting
    fails rather than merely looking plausible.
    """
    from PySide6.QtWidgets import QTabWidget

    window = _window_over([_job("job-1", 0), _job("job-2", 1)], tmp_path)
    body = window.centralWidget()
    assert isinstance(body, QTabWidget)
    assert body.tabText(0) == "Queue (2)", f"the Queue tab reads {body.tabText(0)!r}"


def test_the_count_follows_the_queue(qapp: QApplication, tmp_path: Path) -> None:
    """A count is only useful while it is true.

    Rebuilt from the model on every refresh rather than tracked beside it: a hand-maintained
    count drifts from the list it describes, reliably and in the direction that flatters
    (`ai/TESTING.md` §13's summary rule, applied to a label).
    """
    from PySide6.QtWidgets import QTabWidget

    jobs = [_job("job-1", 0)]
    window = _window_over(jobs, tmp_path)
    body = window.centralWidget()
    assert isinstance(body, QTabWidget)
    assert body.tabText(0) == "Queue (1)"

    jobs.append(_job("job-2", 1))
    window.refresh_queue()

    assert body.tabText(0) == "Queue (2)", (
        f"the queue gained a row and the tab still reads {body.tabText(0)!r}"
    )


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


def test_the_confirmation_names_its_own_count(qapp: QApplication, tmp_path: Path) -> None:
    """`DAT-005` §4: the count and the file guarantee in one breath.

    "Remove" does not say how much is about to go, and a user who selected more than they meant to
    has nothing to notice it by. Singular is written separately because "1 downloads" is the tell
    that a message was assembled rather than composed.
    """
    assert removal_question(1) == "Remove this download from history?"
    assert removal_question(3) == "Remove these 3 downloads from history?"
    assert "downloads" not in removal_question(1), (
        "the singular case reads as a plural, which is how a user learns the message is generated "
        "and stops reading it"
    )


def test_confirming_removes_and_refusing_does_not(qapp: QApplication, tmp_path: Path) -> None:
    """The confirmation is not decoration: **No must do nothing** (`DAT-005` §4).

    Removal is irreversible — there is no soft delete — so the half worth testing is the half that
    protects the user. A dialog whose No branch removed anyway is worse than no dialog, because it
    taught them the click was safe.
    """
    asked: list[list[str]] = []
    window = _window_over([], tmp_path, on_history_removal_requested=asked.append)

    for button, expected in (
        (QMessageBox.StandardButton.No, []),
        (QMessageBox.StandardButton.Yes, [["job-1", "job-2"]]),
    ):
        confirm = window._remove_history(["job-1", "job-2"])
        assert isinstance(confirm, QMessageBox)
        try:
            assert "2 downloads" in confirm.text(), f"the question reads {confirm.text()!r}"
            assert confirm.informativeText() == HISTORY_KEEPS_FILES, (
                "the confirmation does not say the files are safe, which is the one thing a user "
                "about to remove a download needs to know"
            )
            assert confirm.defaultButton() == confirm.button(QMessageBox.StandardButton.No), (
                "the default button removes; an irreversible action's default should be the one "
                "that does nothing"
            )
            confirm.button(button).click()
        finally:
            confirm.close()
        assert asked == expected, f"{button} produced {asked}"


def test_history_says_the_files_are_safe_while_it_is_showing(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`DAT-005` §3: carried permanently, not only in the confirmation.

    A promise that appears in a dialog is a promise only the people who read dialogs have, and
    this one is about somebody's files. Asserted on the *status bar* while the History tab is in
    front, and asserted absent on Queue — a message that never changes is wallpaper.
    """
    from PySide6.QtWidgets import QTabWidget

    window = _window_over([_job("job-1", 0)], tmp_path, history=_FakeHistory())
    body = window.centralWidget()
    assert isinstance(body, QTabWidget)
    history = window.history_view
    assert history is not None, "the window was given a history reader and built no History tab"
    history_tab = body.indexOf(history)
    assert history_tab >= 0, "the window has no History tab to show the promise on"

    body.setCurrentIndex(history_tab)
    assert window.statusBar().currentMessage() == HISTORY_KEEPS_FILES, (
        f"the History tab says {window.statusBar().currentMessage()!r}"
    )

    queue = window.queue_view
    assert queue is not None
    body.setCurrentIndex(body.indexOf(queue))
    assert window.statusBar().currentMessage() != HISTORY_KEEPS_FILES, (
        "the queue carries history's promise too, so it says nothing about history"
    )


class _FakeHistory:
    """A `HistoryReader` over nothing. The promise does not depend on there being records."""

    def all_entries(self) -> list[object]:
        return []
