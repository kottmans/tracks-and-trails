"""The shared row: what it draws, and what it costs (`T-118`, `T-119`).

Every test here is one of `T-119`'s carried acceptance criteria, and each is written to fail for
the reason the criterion names rather than for a nearby one:

- **fields by value, not by pixel** — the roles are read, not the painted image, except where the
  claim really is about what was drawn (the derived tile, which has no textual form);
- **no fetch for a row the view never asked to paint** — a model far larger than any viewport,
  painting a handful of rows, counting requests;
- **a stated cache bound** — exceeded on purpose, asserting that memory is *released* rather than
  that the cache "works";
- **the disk cache** under `NFR-004`'s directory, keyed so two jobs for one URL share one file and
  swept when no job names it any more;
- **repaint cost** at a queue size no hand-driven test reaches.

`RowDelegate.paint` is driven directly rather than through a shown widget. That is not a shortcut:
`paint` is exactly what a view calls per visible row, and painting the rows a test names is the
only way to say "the view never asked for row 900" without depending on a scroll position and a
window size that CI does not have.
"""

import threading
import time
from collections.abc import Callable, Iterator
from itertools import pairwise
from pathlib import Path
from typing import Any, Final

import pytest
from PySide6.QtCore import (
    QAbstractListModel,
    QEvent,
    QModelIndex,
    QPointF,
    QRect,
    QRunnable,
    Qt,
)
from PySide6.QtCore import QPersistentModelIndex as _PersistentIndex
from PySide6.QtGui import QColor, QFontMetrics, QImage, QMouseEvent, QPainter, QPalette
from PySide6.QtWidgets import QApplication, QStyleOptionViewItem

from tracks_and_trails.core.paths import thumbnail_cache_directory, thumbnail_cache_path
from tracks_and_trails.ui import row_delegate
from tracks_and_trails.ui.row_delegate import (
    BAR_HEIGHT,
    CHILD_THUMBNAIL,
    DEPTH_ROLE,
    DETAIL_ROLE,
    EDITOR_WIDTH,
    EXPANDED_ROLE,
    GAP,
    HEADLINE_ROLE,
    HUE_ROLE,
    INDENT,
    JOB_ID_ROLE,
    MENU_ZONE_INSET,
    MERGED_BLOCKS,
    MIN_BLOCK_WIDTH,
    MIN_CONTROL_WIDTH,
    MIN_FRACTION_BAR,
    PADDING,
    PRESET_CHOICES_ROLE,
    PRESET_ROLE,
    PROGRESS_ROLE,
    ROW_HEIGHT,
    SEGMENTS_ROLE,
    SELECTOR_FLAGS,
    SELECTOR_LINES,
    SELECTOR_ROLE,
    STATE_CHIP_ROLE,
    STATE_ROLE,
    TEXT_LINES,
    THUMBNAIL_URL_ROLE,
    TWISTY_WIDTH,
    VERBS_ROLE,
    RowDelegate,
    SegmentState,
    _merge,
    minimum_row_width,
    segment_blocks,
    segment_span,
)
from tracks_and_trails.ui.row_verbs import Verb
from tracks_and_trails.ui.thumbnails import THUMBNAIL_SIZE, ThumbnailStore

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

#: A real image already in this repository, used as thumbnail bytes. Reusing the application icon
#: rather than committing a second PNG: the claim is that Qt decoded *something* into a pixmap.
IMAGE_SOURCE: Final = REPO_ROOT / "src" / "tracks_and_trails" / "resources" / "icons" / "icon.png"

#: The width a row is rendered at here. Wide enough that nothing under test is elided.
RENDER_WIDTH: Final = 700

#: The widths every layout claim is swept across, one pixel at a time (`T-155`, `T-167`).
#:
#: **Swept rather than sampled, and that is `T-155`'s lesson rather than a preference.** Its blocks
#: merged at most widths and not at 800 px, so a test rendering one width drew the defect correctly
#: and would have passed. Every collision on this row — the verbs against the bar, the verbs
#: against the format line, the control against the tile — appears over a *range* and disappears
#: again, so a range is what has to be asserted.
#:
#: The low end is a window narrower than any this application opens at, because a user can drag one
#: there and `T-160` is the record of what was drawn when they did. It was 380 until `T-160`: below
#: that the control took the whole width beside the tile and the row had no last line to measure.
SWEEP_WIDTHS: Final = range(300, 1201)

#: `NFR-001` budgets ~100 ms for an interaction. Half a second here for the same reason the add
#: dialog's tests use that figure: the property is that the call **does not wait**, which a
#: blocking implementation misses by seconds rather than by milliseconds.
INTERACTION_BUDGET_SECONDS: Final = 0.5

#: A queue no hand-driven test reaches, and the size the repaint bound is asserted at.
LARGE_QUEUE: Final = 500

#: How many rows a viewport of a realistic size holds. The number of rows a scroll ever paints at
#: once is what the fetch count is compared against — not the number of rows that exist.
VIEWPORT_ROWS: Final = 12

#: **The repaint budget, with real headroom** (`T118-R10`).
#:
#: `NFR-001` budgets ~100 ms for an interaction, and a repaint is a fraction of one. This is five
#: times that, against a viewport-sized paint that measures in single-digit milliseconds on any
#: machine — deliberately not "the largest number one Linux measurement will bear", which is the
#: sizing that made `T118-R10`'s gate flap between two runs of the same code.
REPAINT_BUDGET_SECONDS: Final = 0.5


class FakeLoader:
    """Hands over bytes without a network, and records what it was asked for."""

    def __init__(self, data: bytes | None) -> None:
        self._data = data
        self.requested: list[str] = []
        self.cancels = 0

    def load(self, url: str, done: Callable[[bytes | None], None]) -> None:
        self.requested.append(url)
        done(self._data)

    def cancel(self) -> None:
        self.cancels += 1


class RowsModel(QAbstractListModel):
    """A list of rows answering the delegate's roles, and nothing else.

    A bare model rather than either real one: the claims here are about the delegate and the
    store, and driving them through `StagingModel` or `QueueModel` would make a failure ambiguous
    between the three.
    """

    def __init__(self, rows: list[dict[int, Any]]) -> None:
        super().__init__()
        self._rows = rows

    # Qt's override names, hence the camelCase. The index type is the union Qt's own signature
    # uses — narrowing it to `QModelIndex` is a Liskov violation that only the unscoped `mypy`
    # gate can see (`ai/TESTING.md` §12).
    def rowCount(self, parent: QModelIndex | _PersistentIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._rows)

    def data(
        self, index: QModelIndex | _PersistentIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        return self._rows[index.row()].get(role)


def a_row(
    index: int, *, thumbnail: str | None = None, extra: dict[int, Any] | None = None
) -> dict[int, Any]:
    """One row's roles. `extra` is a dict rather than keyword arguments because the roles are
    integers, and `**{ROLE: value}` is a `TypeError` — keywords must be strings."""
    row: dict[int, Any] = {
        HEADLINE_ROLE: f"Clip number {index}",
        DETAIL_ROLE: f"Uploader {index} · 3:21 · Single item",
        STATE_ROLE: "Read",
        HUE_ROLE: (index * 37) % 360,
        THUMBNAIL_URL_ROLE: thumbnail,
    }
    row.update(extra or {})
    return row


@pytest.fixture
def stores(qapp: QApplication, tmp_path: Path) -> Iterator[Callable[..., ThumbnailStore]]:
    """Builds stores and closes them, so no worker outlives the test that started it."""
    built: list[ThumbnailStore] = []

    def build(**kwargs: Any) -> ThumbnailStore:
        kwargs.setdefault("cache_root", tmp_path / "cache")
        store = ThumbnailStore(**kwargs)
        built.append(store)
        return store

    yield build

    for store in built:
        store.close()
    # `close()` deliberately does not wait (`T118-R13`), so the *fixture* waits — a test's own
    # teardown is not the GUI thread and is exactly where a bounded wait belongs.
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and any(store.outstanding for store in built):
        qapp.processEvents()
        time.sleep(0.005)
    qapp.processEvents()


def spin_until(qapp: QApplication, predicate: Callable[[], bool], timeout: float = 30) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        qapp.processEvents()
        time.sleep(0.005)
    return predicate()


def holds(store: ThumbnailStore, url: str) -> Callable[[], bool]:
    """A `spin_until` predicate bound to `url` **now**, rather than when it is called.

    A function rather than a `lambda` in the loop: closing over the loop variable is what `B023`
    flags and what the `lambda url=url:` trick works around, and that trick in turn defeats mypy's
    inference. Binding through a parameter satisfies both and says what it means.
    """
    return lambda: url in store.cached_urls


def paint_rows(
    model: RowsModel,
    delegate: RowDelegate,
    *indices: int,
    width: int = RENDER_WIDTH,
    height: int = ROW_HEIGHT,
) -> QImage:
    """Paint the named rows exactly as a view paints its visible ones.

    **The only route to a thumbnail**, which is what makes "row 900 was never painted" a statement
    about this call list rather than about a scroll position.

    `height` is `ROW_HEIGHT` by default, which is what a row with nothing on its third line gets.
    A row that draws a format line needs what `sizeHint` would give it — see `FULL_ROW_HEIGHT`,
    and note that painting such a row at `ROW_HEIGHT` silently squeezes the last line to a couple
    of pixels rather than failing.
    """
    image = QImage(width, height * max(len(indices), 1), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        for slot, index in enumerate(indices):
            option = QStyleOptionViewItem()
            option.rect = QRect(0, slot * height, width, height)
            option.fontMetrics = QFontMetrics(option.font)
            delegate.paint(painter, option, model.index(index, 0))
    finally:
        painter.end()
    return image


def tile_colour(image: QImage, slot: int = 0) -> QColor:
    return QColor(image.pixel(PADDING + 4, slot * ROW_HEIGHT + PADDING + 4))


# --- 1. the row is as tall as what it contains (`T118-R7`) -------------------------------------


def test_a_row_is_tall_enough_for_the_thumbnail_it_draws(qapp: QApplication) -> None:
    """`T118-R7`: a 54 px thumbnail was being clipped into a 25 px row.

    Asserted against `THUMBNAIL_SIZE` rather than against the number 66, so changing the thumbnail
    and forgetting the row is a failure here rather than a clipped picture on screen.
    """
    delegate = RowDelegate()
    model = RowsModel([a_row(0)])
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, RENDER_WIDTH, 0)
    option.fontMetrics = QFontMetrics(option.font)

    height = delegate.sizeHint(option, model.index(0, 0)).height()

    assert height >= THUMBNAIL_SIZE[1], (
        f"a row is {height} px tall and must hold a {THUMBNAIL_SIZE[1]} px thumbnail"
    )
    # And the row's own line budget, in the view's own font — the same defect approached from the
    # other side, which is what a large accessibility font would produce. `TEXT_LINES`, not the
    # literal 3 this asserted while the row drew four: a constant the test does not share with the
    # code is a constant the test cannot police.
    assert height >= TEXT_LINES * QFontMetrics(option.font).height()


def test_every_row_is_the_same_height_whatever_it_holds(qapp: QApplication) -> None:
    """Uniform rows are what let a long list compute its visible range instead of measuring it."""
    delegate = RowDelegate()
    model = RowsModel(
        [
            a_row(0),
            a_row(1, extra={HEADLINE_ROLE: "x" * 4000, DETAIL_ROLE: "y" * 4000}),
            {HEADLINE_ROLE: "bare"},
        ]
    )
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, RENDER_WIDTH, 0)
    option.fontMetrics = QFontMetrics(option.font)

    heights = {delegate.sizeHint(option, model.index(i, 0)).height() for i in range(3)}

    assert len(heights) == 1, f"rows differ in height: {heights}"


def test_a_running_chip_carries_progress_without_erasing_the_worker_stage(
    qapp: QApplication,
) -> None:
    """Reviewer regression for T-130's ``62%`` chip and the existing stage line.

    The chip is the compact progress value the accepted amendment names. That stops it duplicating
    the longer worker stage; it does not make the stage expendable. Compare two stages under one
    fraction: the title-line chip must be identical, while the whole rows must differ because the
    second line still says which work the worker is doing.
    """
    # `STATE_CHIP_ROLE` carries the chip's *text* since `T130-R3`; it was a flag when this
    # regression was written, and with a flag the delegate now draws no chip at all and both
    # assertions below pass without measuring anything. Amended on the maintainer's instruction of
    # 2026-08-04 to supply the text the model computes, which is what puts the claims back.
    common: dict[int, Any] = {
        HEADLINE_ROLE: "Cairngorms trail run",
        DETAIL_ROLE: "Hill & Bothy · 12:04",
        STATE_CHIP_ROLE: "62%",
        PROGRESS_ROLE: 0.62,
        HUE_ROLE: 0,
    }
    downloading = RowsModel([{**common, STATE_ROLE: "Downloading video"}])
    postprocessing = RowsModel([{**common, STATE_ROLE: "Post-processing"}])
    delegate = RowDelegate()
    first = paint_rows(downloading, delegate, 0)
    second = paint_rows(postprocessing, delegate, 0)

    # A generous crop around the chip. Both rows have one PROGRESS_ROLE, so changing STATE_ROLE
    # must not alter anything here; the old implementation put the worker stage in this rectangle.
    chip_line = QRect(RENDER_WIDTH - 180, 0, 180, PADDING + QFontMetrics(qapp.font()).height())
    assert first.copy(chip_line) == second.copy(chip_line), (
        "changing the worker stage changed the title-line chip, so it is not derived from the "
        "shared 62% progress value"
    )

    assert first != second, (
        "changing 'Downloading video' to 'Post-processing' changed no drawn pixel; the 62% chip "
        "replaced the worker stage instead of leaving it on the second line"
    )


def test_a_completed_chip_says_done_instead_of_turning_completion_into_progress(
    qapp: QApplication,
) -> None:
    """The adopted terminal chip is ``Done``; 100% is only a running-progress shape.

    **Which word is the model's half of this finding, so it is asserted at the model** — see
    ``test_a_completed_queue_row_chips_done_rather_than_100_percent``. What is left here is the
    delegate's half, and it is the half that caused the defect: the chip used to be derived from
    ``PROGRESS_ROLE``, and a completed job reports a fraction of exactly 1.0, so completion was
    rendered as progress. So: **one chip text, two fractions.** The drawn chip must not move.

    Amended on the maintainer's instruction of 2026-08-04, with the role now carrying text.
    Against the derived implementation this fails, drawing ``100%`` beside ``Done``.
    """
    common: dict[int, Any] = {
        HEADLINE_ROLE: "Packing for the WHW",
        DETAIL_ROLE: "10.2 MB",
        STATE_CHIP_ROLE: "Done",
        STATE_ROLE: "Completed",
        HUE_ROLE: 0,
    }
    finished = RowsModel([{**common, PROGRESS_ROLE: 1.0}])
    without_a_fraction = RowsModel([{**common, PROGRESS_ROLE: None}])
    delegate = RowDelegate()
    current_image = paint_rows(finished, delegate, 0)
    adopted_image = paint_rows(without_a_fraction, delegate, 0)

    chip_line = QRect(RENDER_WIDTH - 180, 0, 180, PADDING + QFontMetrics(qapp.font()).height())
    assert current_image.copy(chip_line) == adopted_image.copy(chip_line), (
        "a completed row draws '100%' where UX-005 adopted the terminal chip 'Done'; the chip is "
        "reading PROGRESS_ROLE instead of the text the model supplies"
    )


def test_a_row_with_choices_draws_a_control_and_one_without_does_not(
    qapp: QApplication,
) -> None:
    """`UX-004` §1, `T118-R12`: the control is **drawn on the row**, not merely available.

    The delegate reserved `EDITOR_WIDTH` and painted nothing in it, so the override existed only
    for a user who already knew to press F2 or right-click. `UX-004` put the control on the row
    precisely to stop that, and its `T-119` sequencing note permits *one reused widget* — not an
    empty slot.

    **Two rows identical apart from `PRESET_CHOICES_ROLE`**, and both with empty text, so the only
    thing that can differ in the compared rectangle is the control. Asserting "the slot is not
    blank" instead would pass with the control disabled, because the item background fills it —
    which an earlier version of this test did.
    """
    delegate = RowDelegate()
    blank_roles: dict[int, Any] = {HEADLINE_ROLE: "", DETAIL_ROLE: "", STATE_ROLE: "", HUE_ROLE: 0}
    with_control = RowsModel([{**blank_roles, PRESET_CHOICES_ROLE: ("Best video", "Audio only")}])
    without = RowsModel([dict(blank_roles)])

    drawn = paint_rows(with_control, delegate, 0)
    plain = paint_rows(without, delegate, 0)

    slot = QRect(
        RENDER_WIDTH - PADDING - EDITOR_WIDTH, PADDING, EDITOR_WIDTH, ROW_HEIGHT - 2 * PADDING
    )
    assert drawn.copy(slot) != plain.copy(slot), (
        "a row offering format choices drew the same slot as one offering none, so no control "
        "was painted"
    )
    # And only there: a control must not redraw the rest of the row differently.
    rest = QRect(0, 0, RENDER_WIDTH - PADDING - EDITOR_WIDTH - GAP, ROW_HEIGHT)
    assert drawn.copy(rest) == plain.copy(rest), "painting the control disturbed the row's text"


def test_the_control_shows_the_rows_own_choice(qapp: QApplication) -> None:
    """The drawn control carries the row's current value, not a blank (`T118-R4`, `UX-004`)."""
    delegate = RowDelegate()
    blank_roles: dict[int, Any] = {HEADLINE_ROLE: "", DETAIL_ROLE: "", STATE_ROLE: "", HUE_ROLE: 0}
    choices = ("Best video", "Audio only")
    inherited = RowsModel([{**blank_roles, PRESET_CHOICES_ROLE: choices}])
    overridden = RowsModel(
        [{**blank_roles, PRESET_CHOICES_ROLE: choices, PRESET_ROLE: "Audio only"}]
    )

    slot = QRect(
        RENDER_WIDTH - PADDING - EDITOR_WIDTH, PADDING, EDITOR_WIDTH, ROW_HEIGHT - 2 * PADDING
    )
    assert paint_rows(inherited, delegate, 0).copy(slot) != paint_rows(
        overridden, delegate, 0
    ).copy(slot), "an inherited row and an overridden row drew the same control"


# --- 2. no fetch for a row the view never asked to paint ---------------------------------------


def test_no_thumbnail_is_fetched_for_a_row_that_is_never_painted(
    qapp: QApplication, stores: Callable[..., ThumbnailStore]
) -> None:
    """`T-119`: **the criterion, at a size where getting it wrong is unmissable.**

    Five hundred rows, twelve painted. A design that fetched when a row was *created* — which is
    what the dialog did before this — would issue five hundred requests here, so the correct
    answer and the wrong one differ by a factor of forty rather than by a boundary case.
    """
    loader = FakeLoader(IMAGE_SOURCE.read_bytes())
    store = stores(loader=loader)
    delegate = RowDelegate(thumbnails=store)
    model = RowsModel(
        [
            a_row(index, thumbnail=f"https://pics.invalid/{index}.jpg")
            for index in range(LARGE_QUEUE)
        ]
    )

    paint_rows(model, delegate, *range(VIEWPORT_ROWS))
    assert spin_until(qapp, lambda: store.fetches >= VIEWPORT_ROWS)

    assert store.fetches == VIEWPORT_ROWS, (
        f"{store.fetches} thumbnails were fetched for {VIEWPORT_ROWS} painted rows out of "
        f"{LARGE_QUEUE}"
    )
    assert all(f"/{index}.jpg" in "".join(loader.requested) for index in range(VIEWPORT_ROWS))
    assert f"/{LARGE_QUEUE - 1}.jpg" not in "".join(loader.requested), (
        "a row far outside any viewport was fetched"
    )


def test_painting_one_row_repeatedly_fetches_it_once(
    qapp: QApplication, stores: Callable[..., ThumbnailStore]
) -> None:
    """A row repaints constantly; a fetch per repaint would be a request loop."""
    loader = FakeLoader(IMAGE_SOURCE.read_bytes())
    store = stores(loader=loader)
    delegate = RowDelegate(thumbnails=store)
    model = RowsModel([a_row(0, thumbnail="https://pics.invalid/only.jpg")])

    for _ in range(20):
        paint_rows(model, delegate, 0)
        qapp.processEvents()
    assert spin_until(qapp, lambda: store.peek("https://pics.invalid/only.jpg") is not None)
    for _ in range(20):
        paint_rows(model, delegate, 0)
        qapp.processEvents()

    assert store.fetches == 1, f"one row fetched its picture {store.fetches} times"


# --- 3. the cache has a stated bound, and releases beyond it -----------------------------------


def test_the_pixmap_cache_releases_what_it_evicts(
    qapp: QApplication, stores: Callable[..., ThumbnailStore]
) -> None:
    """`T-119`: **memory is released**, not merely "the cache works".

    Asserted on what the cache *no longer holds* after the bound is exceeded, and on the identity
    of what it dropped: least recently used first. A test that only asserted a hit on the newest
    entry would pass against a cache that grew without limit.
    """
    limit = 4
    loader = FakeLoader(IMAGE_SOURCE.read_bytes())
    store = stores(loader=loader, pixmap_limit=limit)
    delegate = RowDelegate(thumbnails=store)
    over = limit * 3
    model = RowsModel(
        [a_row(index, thumbnail=f"https://pics.invalid/{index}.jpg") for index in range(over)]
    )

    for index in range(over):
        url = f"https://pics.invalid/{index}.jpg"
        paint_rows(model, delegate, index)
        assert spin_until(qapp, holds(store, url)), f"row {index}'s picture never arrived"

    assert len(store.cached_urls) == limit, (
        f"the cache holds {len(store.cached_urls)} pixmaps against a stated bound of {limit}"
    )
    assert store.cached_urls == tuple(
        f"https://pics.invalid/{index}.jpg" for index in range(over - limit, over)
    ), "eviction did not drop the least recently used"
    assert store.peek("https://pics.invalid/0.jpg") is None, "an evicted pixmap is still held"


def test_using_a_cached_pixmap_keeps_it_from_being_evicted(
    qapp: QApplication, stores: Callable[..., ThumbnailStore]
) -> None:
    """Least recently *used*, not least recently added — or scrolling evicts what is on screen."""
    limit = 3
    store = stores(loader=FakeLoader(IMAGE_SOURCE.read_bytes()), pixmap_limit=limit)
    delegate = RowDelegate(thumbnails=store)
    model = RowsModel(
        [a_row(index, thumbnail=f"https://pics.invalid/{index}.jpg") for index in range(limit + 1)]
    )

    for index in range(limit):
        url = f"https://pics.invalid/{index}.jpg"
        paint_rows(model, delegate, index)
        assert spin_until(qapp, holds(store, url))

    # Touch the oldest, then overflow the cache by one.
    paint_rows(model, delegate, 0)
    paint_rows(model, delegate, limit)
    assert spin_until(qapp, lambda: f"https://pics.invalid/{limit}.jpg" in store.cached_urls)

    assert store.peek("https://pics.invalid/0.jpg") is not None, (
        "the pixmap used most recently was evicted, so scrolling drops what is on screen"
    )
    assert store.peek("https://pics.invalid/1.jpg") is None


# --- 4. the disk cache (`NFR-004`) --------------------------------------------------------------


def test_a_fetched_thumbnail_is_written_under_the_cache_directory(
    qapp: QApplication, stores: Callable[..., ThumbnailStore], tmp_path: Path
) -> None:
    """`NFR-004`: a cache directory, never beside the application."""
    root = tmp_path / "cache"
    store = stores(loader=FakeLoader(IMAGE_SOURCE.read_bytes()), cache_root=root)
    delegate = RowDelegate(thumbnails=store)
    url = "https://pics.invalid/one.jpg"
    model = RowsModel([a_row(0, thumbnail=url)])

    paint_rows(model, delegate, 0)
    # Waits on the decode rather than on the file existing: the write is what precedes it, so this
    # cannot observe a half-written cache entry the way an `exists()` poll can.
    assert spin_until(qapp, lambda: store.peek(url) is not None)

    written = thumbnail_cache_path(url, root)
    assert written.exists(), "the decoded thumbnail was never written to the cache"
    assert written.parent == thumbnail_cache_directory(root)
    assert written.read_bytes() == IMAGE_SOURCE.read_bytes()


def test_two_jobs_for_one_url_share_one_cached_file(
    qapp: QApplication, stores: Callable[..., ThumbnailStore], tmp_path: Path
) -> None:
    """`T-119`: keyed so two jobs for one URL share it.

    Two rows, one thumbnail URL, and the assertion is on the **directory's contents** rather than
    on a hit count: a key that included the row would produce two files here, and a cache that
    merely deduplicated in memory would still produce two.
    """
    root = tmp_path / "cache"
    loader = FakeLoader(IMAGE_SOURCE.read_bytes())
    store = stores(loader=loader, cache_root=root)
    delegate = RowDelegate(thumbnails=store)
    url = "https://pics.invalid/shared.jpg"
    model = RowsModel([a_row(0, thumbnail=url), a_row(1, thumbnail=url)])

    paint_rows(model, delegate, 0, 1)
    assert spin_until(qapp, lambda: thumbnail_cache_path(url, root).exists())
    paint_rows(model, delegate, 0, 1)
    qapp.processEvents()

    assert list(thumbnail_cache_directory(root).iterdir()) == [thumbnail_cache_path(url, root)]
    assert loader.requested == [url], f"one picture was fetched {len(loader.requested)} times"


def test_a_cached_thumbnail_is_not_fetched_again(
    qapp: QApplication, stores: Callable[..., ThumbnailStore], tmp_path: Path
) -> None:
    """The disk cache makes a relaunch free — so a second store must not go to the network."""
    root = tmp_path / "cache"
    url = "https://pics.invalid/kept.jpg"
    first = stores(loader=FakeLoader(IMAGE_SOURCE.read_bytes()), cache_root=root)
    model = RowsModel([a_row(0, thumbnail=url)])
    paint_rows(model, RowDelegate(thumbnails=first), 0)
    assert spin_until(qapp, lambda: thumbnail_cache_path(url, root).exists())

    later = FakeLoader(IMAGE_SOURCE.read_bytes())
    second = stores(loader=later, cache_root=root)
    paint_rows(model, RowDelegate(thumbnails=second), 0)
    assert spin_until(qapp, lambda: second.peek(url) is not None), "the cached file was not used"

    assert later.requested == [], "a cached thumbnail was fetched over the network again"
    assert second.fetches == 0


def test_sweeping_removes_what_no_job_names_and_keeps_what_one_does(
    qapp: QApplication, stores: Callable[..., ThumbnailStore], tmp_path: Path
) -> None:
    """`T-119`: removed with the job — **and only when no remaining job names it**.

    The two halves of the criterion pull opposite ways, so both are asserted in one arrangement:
    a URL nothing references any more goes, and a URL a surviving job still references stays.
    """
    root = tmp_path / "cache"
    store = stores(loader=FakeLoader(IMAGE_SOURCE.read_bytes()), cache_root=root)
    delegate = RowDelegate(thumbnails=store)
    kept = "https://pics.invalid/kept.jpg"
    gone = "https://pics.invalid/gone.jpg"
    model = RowsModel([a_row(0, thumbnail=kept), a_row(1, thumbnail=gone)])

    paint_rows(model, delegate, 0, 1)
    assert spin_until(
        qapp,
        lambda: (
            thumbnail_cache_path(kept, root).exists() and thumbnail_cache_path(gone, root).exists()
        ),
    )

    swept: list[int] = []
    store.swept.connect(swept.append)
    store.sweep({kept})
    assert spin_until(qapp, lambda: bool(swept)), "the sweep never reported"

    assert swept == [1]
    assert thumbnail_cache_path(kept, root).exists(), "a picture a live job still names was deleted"
    assert not thumbnail_cache_path(gone, root).exists(), "a picture nothing names survived"


# --- 4b. the lifecycle never blocks the GUI thread (`T118-R13`) --------------------------------


class _Blocker(QRunnable):
    """Occupies a pool thread until released.

    The pool is filled with these so the assertions below are about **scheduling**, not about
    speed: if a UI call did its work inline it would finish regardless of how busy the pool is,
    and if it schedules then the work provably has not happened yet. That is a deterministic
    statement where a stopwatch would be a race.
    """

    def __init__(self, gate: threading.Event) -> None:
        super().__init__()
        self._gate = gate

    def run(self) -> None:
        self._gate.wait(timeout=30)


def occupy_pool(store: ThumbnailStore, gate: threading.Event) -> None:
    """Fill every thread of **the pool this store schedules on**.

    Asked of the store rather than fetched from the module, because the claim is about whichever
    pool is really in use. An earlier version reached for the shared pool by name and therefore
    passed against a mutation that handed the store a private child pool — reintroducing exactly
    the ownership defect `T118-R13` reported.
    """
    for _ in range(store.pool.maxThreadCount()):
        store.pool.start(_Blocker(gate))


def test_sweeping_schedules_the_disk_work_instead_of_doing_it(
    qapp: QApplication, stores: Callable[..., ThumbnailStore], tmp_path: Path
) -> None:
    """`T118-R13`, `ARC-005`: cache deletion is disk work and must not run on the GUI thread.

    `sweep()` enumerated the directory, stat'd every entry and unlinked inline — from *every* queue
    model reset, which a removal, a reorder and a clear all cause. A long history on a slow or
    networked cache directory would have paid for that on the thread drawing the window.

    Proven by blocking the pool: if the call returns while no worker can run, the deletion cannot
    have happened inline, and the doomed file is still there to prove it.
    """
    root = tmp_path / "cache"
    store = stores(loader=FakeLoader(IMAGE_SOURCE.read_bytes()), cache_root=root)
    doomed = thumbnail_cache_path("https://pics.invalid/gone.jpg", root)
    doomed.parent.mkdir(parents=True, exist_ok=True)
    doomed.write_bytes(b"stale")

    gate = threading.Event()
    occupy_pool(store, gate)
    try:
        started = time.perf_counter()
        store.sweep(set())
        elapsed = time.perf_counter() - started

        assert elapsed < INTERACTION_BUDGET_SECONDS, (
            f"sweep() held the GUI thread for {elapsed:.3f}s"
        )
        assert doomed.exists(), "the file was deleted inline; the sweep did not go to the pool"
        assert store.outstanding, "no pool work was scheduled, so nothing will ever sweep"
    finally:
        gate.set()

    swept: list[int] = []
    store.swept.connect(swept.append)
    assert spin_until(qapp, lambda: bool(swept)), "the scheduled sweep never ran"
    assert not doomed.exists(), "the sweep ran but deleted nothing"


def test_closing_returns_without_waiting_for_the_pool(
    qapp: QApplication, stores: Callable[..., ThumbnailStore]
) -> None:
    """`T118-R13`: `close()` ran `waitForDone(5000)` on the GUI thread.

    That is an explicit five-second stall on the thread drawing the window, at the moment the user
    asked for the dialog to go away. Closing now marks the store closed, cancels network work and
    returns; ownership completes from `closed` when the last pool task drains.

    Blocked pool again, so "returned without waiting" is a fact rather than a measurement — and
    `closed` must **not** have been emitted while a task is still outstanding, or the signal would
    be lying about the thing it exists to report.
    """
    loader = FakeLoader(IMAGE_SOURCE.read_bytes())
    store = stores(loader=loader)
    finished: list[bool] = []
    store.closed.connect(lambda: finished.append(True))

    gate = threading.Event()
    occupy_pool(store, gate)
    # A task **of the store's own**, queued behind the blockers so it cannot finish. The blockers
    # alone would not do: `outstanding` counts what this store started, and a first draft of this
    # test asserted against foreign pool work and failed for that reason rather than for the one
    # it names.
    store.pixmap("https://pics.invalid/queued.jpg")
    assert store.outstanding == 1, "the fetch did not reach the pool, so nothing is outstanding"

    try:
        started = time.perf_counter()
        store.close()
        elapsed = time.perf_counter() - started

        assert elapsed < INTERACTION_BUDGET_SECONDS, (
            f"close() held the GUI thread for {elapsed:.3f}s against a blocked pool"
        )
        assert loader.cancels == 1, "closing did not cancel network work"
        qapp.processEvents()
        assert finished == [], "closed was announced while a pool task was still running"
    finally:
        gate.set()

    assert spin_until(qapp, lambda: bool(finished)), "closed was never announced after draining"


def test_deleting_a_closed_store_neither_waits_nor_is_emitted_through(
    qapp: QApplication, tmp_path: Path
) -> None:
    """`T118-R13`, **the half that was not resolved**: `close()` returned, and *deletion* blocked.

    The first correction moved the wait out of `close()` and reasoned that `QThreadPool`'s
    destructor would cover the rest "when the store is destroyed, rather than on the interaction".
    Backwards: the pool was the store's **child**, so deleting the store ran that destructor on the
    GUI thread — the reviewer measured 1.008 s — and the runnables emitted through the store
    itself, which a Python reference does not keep alive on the C++ side. `_ReadFromDisk` then
    raised `RuntimeError: Signal source has been deleted`, which is a lost worker completion.

    This asserts both halves at once, against a blocked pool so neither is a stopwatch reading:
    the delete returns inside the budget, and the task that outlives the store emits without
    raising.
    """
    store = ThumbnailStore(loader=FakeLoader(IMAGE_SOURCE.read_bytes()), cache_root=tmp_path / "c")
    gate = threading.Event()
    occupy_pool(store, gate)
    store.pixmap("https://pics.invalid/outlives.jpg")
    assert store.outstanding == 1, "no store-owned task is queued, so this proves nothing"

    faults: list[BaseException | None] = []
    original = threading.excepthook

    def record(args: threading.ExceptHookArgs) -> None:
        """Capture anything a pool thread raises. `exc_value` is optional in the hook's own type,
        so the list admits `None` rather than the assertion below being written around a cast."""
        faults.append(args.exc_value)

    threading.excepthook = record
    try:
        store.close()
        started = time.perf_counter()
        store.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        elapsed = time.perf_counter() - started

        assert elapsed < INTERACTION_BUDGET_SECONDS, (
            f"deleting the store held the GUI thread for {elapsed:.3f}s while the pool was busy"
        )

        gate.set()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and store.pool.activeThreadCount():
            qapp.processEvents()
            time.sleep(0.005)
        qapp.processEvents()
    finally:
        gate.set()
        threading.excepthook = original

    assert faults == [], (
        f"a worker raised after the store was deleted: {faults!r} — the task is emitting through a "
        "dead QObject rather than through the sink"
    )


# --- 5. a missing picture is not a failure ------------------------------------------------------


def test_a_row_with_no_picture_draws_its_derived_tile(
    qapp: QApplication, stores: Callable[..., ThumbnailStore]
) -> None:
    """`UX-003`: never an empty well, and never the same well twice."""
    store = stores(loader=FakeLoader(None))
    delegate = RowDelegate(thumbnails=store)
    model = RowsModel([a_row(0), a_row(7)])

    drawn = paint_rows(model, delegate, 0, 1)

    background = QColor(drawn.pixel(RENDER_WIDTH - 1, ROW_HEIGHT - 1))
    assert tile_colour(drawn, 0) != background
    assert tile_colour(drawn, 1) != background
    assert tile_colour(drawn, 0) != tile_colour(drawn, 1), (
        "two rows drew the same derived tile, so it distinguishes nothing (NFR-005)"
    )


def test_a_thumbnail_that_will_not_fetch_is_never_asked_for_again(
    qapp: QApplication, stores: Callable[..., ThumbnailStore]
) -> None:
    """`T-119`: does not retry in a loop, and is not reported as an error.

    A repaint happens whenever anything on the row changes, which for a running download is
    several times a second. Retrying there would be a request per repaint at a URL already known
    to fail.
    """
    loader = FakeLoader(None)
    store = stores(loader=loader)
    delegate = RowDelegate(thumbnails=store)
    model = RowsModel([a_row(0, thumbnail="https://pics.invalid/missing.jpg")])

    paint_rows(model, delegate, 0)
    assert spin_until(qapp, lambda: store.fetches == 1)
    for _ in range(20):
        paint_rows(model, delegate, 0)
        qapp.processEvents()

    assert store.fetches == 1, f"a failed thumbnail was re-fetched {store.fetches} times"
    assert loader.requested == ["https://pics.invalid/missing.jpg"]


# --- 6. repaint cost, at a size no hand-driven test reaches -------------------------------------


def test_painting_a_viewport_of_a_large_queue_stays_inside_the_budget(
    qapp: QApplication, stores: Callable[..., ThumbnailStore]
) -> None:
    """`T-119`'s repaint criterion, and **`T118-R10`'s bound done with headroom**.

    The property is that painting costs what the *viewport* holds and not what the model holds,
    which is what a delegate buys over a widget per row. So the model is `LARGE_QUEUE` and the
    measurement is a viewport — a design whose cost grew with the model would miss this by
    seconds, not by milliseconds.

    **The margin is deliberate** (`T083-R2`, `T118-R10`). `REPAINT_BUDGET_SECONDS` is five times
    `NFR-001`'s whole-interaction budget for work that measures in single-digit milliseconds, so
    the gate distinguishes "cost is proportional to the model" from "cost is proportional to the
    screen" and nothing finer. Sizing it to the fastest machine is exactly what made `T118-R10`
    pass and fail on two runs of unchanged code.
    """
    store = stores(loader=FakeLoader(IMAGE_SOURCE.read_bytes()))
    delegate = RowDelegate(thumbnails=store)
    model = RowsModel(
        [
            a_row(index, thumbnail=f"https://pics.invalid/{index}.jpg")
            for index in range(LARGE_QUEUE)
        ]
    )

    started = time.perf_counter()
    paint_rows(model, delegate, *range(VIEWPORT_ROWS))
    elapsed = time.perf_counter() - started

    assert elapsed < REPAINT_BUDGET_SECONDS, (
        f"painting {VIEWPORT_ROWS} rows of a {LARGE_QUEUE}-row model took {elapsed:.3f}s, over "
        f"the {REPAINT_BUDGET_SECONDS}s budget"
    )


def test_painting_a_viewport_costs_the_same_whatever_the_model_holds(
    qapp: QApplication, stores: Callable[..., ThumbnailStore]
) -> None:
    """The claim `T118-R10` is really about, asserted as a **ratio** rather than as a clock reading.

    A wall-clock budget says the machine was fast enough; this says the design does not grow with
    the queue, which is the property that made 150 rows cost 0.722 s.

    **A ratio does not cancel runner speed** (`T-122`, `T118-R17`). This said comparing two
    measurements taken moments apart *"removes the runner-speed term that made that gate flap"*,
    which is the same false claim `T-122` exists to retire one file over: it cancels a **sustained**
    speed difference and not a **transient** pause, and a stall landing in one of two samples moves
    the ratio arbitrarily. What keeps this one usable — and is why it stays a gate where
    `test_add_dialog`'s became a diagnostic — is that both sides are in-process paint loops of five
    iterations each, on a synthetic model, with an absolute `+ 0.05` floor that dominates at these
    magnitudes. That is a narrower claim than the sentence it replaces, and it is the true one.
    """
    store = stores(loader=FakeLoader(None))
    delegate = RowDelegate(thumbnails=store)
    small = RowsModel([a_row(index) for index in range(VIEWPORT_ROWS)])
    large = RowsModel([a_row(index) for index in range(LARGE_QUEUE)])

    def cost(model: RowsModel) -> float:
        paint_rows(model, delegate, *range(VIEWPORT_ROWS))  # warm the paths
        started = time.perf_counter()
        for _ in range(5):
            paint_rows(model, delegate, *range(VIEWPORT_ROWS))
        return time.perf_counter() - started

    small_cost = cost(small)
    large_cost = cost(large)

    assert large_cost < small_cost * 4 + 0.05, (
        f"painting a viewport of {LARGE_QUEUE} rows cost {large_cost:.4f}s against "
        f"{small_cost:.4f}s for {VIEWPORT_ROWS} rows — the cost is growing with the model"
    )


# --- 7. the fields, by value --------------------------------------------------------------------


def test_a_row_that_answers_no_roles_still_draws(qapp: QApplication) -> None:
    """A model need answer only what it has. Nothing here may raise on an absent role."""
    delegate = RowDelegate()
    model = RowsModel([{}])

    paint_rows(model, delegate, 0)


def test_progress_is_drawn_only_when_there_is_an_honest_fraction(
    qapp: QApplication, stores: Callable[..., ThumbnailStore]
) -> None:
    """`None` is not zero: an unknown total draws no bar rather than an empty one at 0%."""
    delegate = RowDelegate(thumbnails=stores(loader=FakeLoader(None)))
    known = RowsModel([a_row(0, extra={PROGRESS_ROLE: 0.5})])
    unknown = RowsModel([a_row(0, extra={PROGRESS_ROLE: None})])

    with_bar = paint_rows(known, delegate, 0)
    without = paint_rows(unknown, delegate, 0)

    assert with_bar != without, "a row with a known fraction drew the same as one without"


# --- T-140: a playlist as a row that opens ----------------------------------------------------


def test_a_group_row_draws_a_disclosure_and_an_ordinary_row_does_not(qapp: QApplication) -> None:
    """`UX-005` row 9: the triangle is what says this row opens.

    **Three states, because absent and closed are different answers.** `EXPANDED_ROLE` is `True`,
    `False` or missing, and missing means "not a playlist" — the same three-valued shape
    `PRESET_INHERITABLE_ROLE` established at `T126-R4`. A test comparing only open against closed
    would pass with every row growing a triangle.
    """
    common: dict[int, Any] = {HEADLINE_ROLE: "Trail Sounds", DETAIL_ROLE: "16 items", HUE_ROLE: 0}
    plain = paint_rows(RowsModel([common]), RowDelegate(), 0)
    closed = paint_rows(RowsModel([{**common, EXPANDED_ROLE: False}]), RowDelegate(), 0)
    opened = paint_rows(RowsModel([{**common, EXPANDED_ROLE: True}]), RowDelegate(), 0)

    assert plain != closed, "a playlist row draws no disclosure, so nothing says it opens"
    assert closed != opened, (
        "the disclosure looks identical open and closed, so it reports no state"
    )


def test_a_child_row_is_shorter_than_the_group_above_it(qapp: QApplication) -> None:
    """`UX-005` row 9c: shorter, not merely indented.

    An entry inherits its group's format, so its third and fourth lines have nothing to say.
    Drawing it at full height to keep `sizeHint` uniform would waste a third of the list on blank
    space in exactly the case — a sixteen-item playlist — with least room to waste.
    """
    delegate = RowDelegate()
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, RENDER_WIDTH, 200)
    option.font = qapp.font()
    option.fontMetrics = QFontMetrics(option.font)
    model = RowsModel(
        [
            {HEADLINE_ROLE: "Trail Sounds", EXPANDED_ROLE: True, HUE_ROLE: 0},
            {HEADLINE_ROLE: "01 Prelude", DEPTH_ROLE: 1, HUE_ROLE: 0},
        ]
    )

    group = delegate.sizeHint(option, model.index(0, 0))
    child = delegate.sizeHint(option, model.index(1, 0))

    assert child.height() < group.height(), (
        f"a child row is {child.height()}px against the group's {group.height()}px, so the indent "
        "costs width and buys nothing back"
    )


def test_a_child_row_is_indented_and_railed_under_its_group(qapp: QApplication) -> None:
    """The rail **and** the indent are what make an entry read as *belonging* (`T-140`).

    **Two claims, asserted separately**, because the first version of this compared whole rows and
    passed with the rail removed — an indent alone changes enough pixels to satisfy "the rows
    differ". A test that survives the mutation of half its own docstring is a test that measures
    one thing and claims two.
    """
    row: dict[int, Any] = {HEADLINE_ROLE: "01 Prelude of Light", DETAIL_ROLE: "4:12", HUE_ROLE: 0}
    top = paint_rows(RowsModel([row]), RowDelegate(), 0)
    nested = paint_rows(RowsModel([{**row, DEPTH_ROLE: 1}]), RowDelegate(), 0)

    def first_opaque(image: QImage) -> int | None:
        """Where the row's tile starts: the leftmost fully-drawn column.

        **Opacity, not any ink.** The rail is drawn at alpha 90 and sits *left* of the tile, so
        "first non-transparent column" answered with the rail on a nested row and with the tile on
        a top-level one — comparing two different things and calling the difference an indent.
        """
        for x in range(image.width()):
            if any(image.pixelColor(x, y).alpha() == 255 for y in range(image.height())):
                return x
        return None

    def has_ink(image: QImage, columns: range) -> bool:
        return any(image.pixel(x, y) != 0 for x in columns for y in range(image.height()))

    top_edge = first_opaque(top)
    nested_edge = first_opaque(nested)
    assert top_edge is not None and nested_edge is not None, "a row drew no tile at all"
    assert nested_edge > top_edge, (
        f"a nested row's tile starts at x={nested_edge} and a top-level one's at x={top_edge}, "
        "so the entry is not indented under its group"
    )

    # And the space the indent opened is not empty: the rail runs down it.
    assert has_ink(nested, range(top_edge, nested_edge)), (
        "the indent opened a blank gap, so an entry reads as merely shifted rather than as joined "
        "to the group above it"
    )


def test_a_groups_bar_is_segmented_and_shows_a_failure(qapp: QApplication) -> None:
    """`UX-005` row 9b, and the specific lie it exists to prevent.

    Under one continuous bar a playlist that quietly skipped a track looks exactly like one that
    got everything. **Same number of done entries, one of them failed instead of waiting** — a bar
    that reported only "how many finished" would draw these two identically.
    """
    common: dict[int, Any] = {HEADLINE_ROLE: "Trail Sounds", EXPANDED_ROLE: False, HUE_ROLE: 0}
    healthy = [SegmentState.DONE, SegmentState.DONE, SegmentState.WAITING, SegmentState.WAITING]
    broken = [SegmentState.DONE, SegmentState.DONE, SegmentState.FAILED, SegmentState.WAITING]

    fine = paint_rows(RowsModel([{**common, SEGMENTS_ROLE: healthy}]), RowDelegate(), 0)
    failed = paint_rows(RowsModel([{**common, SEGMENTS_ROLE: broken}]), RowDelegate(), 0)

    assert fine != failed, (
        "a failed entry draws the same as one still waiting, so a playlist that skipped a track "
        "looks like one that got everything"
    )


def test_a_group_needs_no_fraction_to_draw_its_progress(qapp: QApplication) -> None:
    """A group answers no `PROGRESS_ROLE`, and that is the point (`UX-005` row 9a).

    Sixteen files whose sizes arrive one at a time give a denominator that grows while it runs, so
    a fraction across them goes *backwards*. The segments must draw without one.
    """
    blank = paint_rows(
        RowsModel([{HEADLINE_ROLE: "Trail Sounds", EXPANDED_ROLE: False, HUE_ROLE: 0}]),
        RowDelegate(),
        0,
    )
    segmented = paint_rows(
        RowsModel(
            [
                {
                    HEADLINE_ROLE: "Trail Sounds",
                    EXPANDED_ROLE: False,
                    HUE_ROLE: 0,
                    SEGMENTS_ROLE: [SegmentState.DONE, SegmentState.WAITING],
                }
            ]
        ),
        RowDelegate(),
        0,
    )

    assert blank != segmented, (
        "the segmented bar was not drawn without a PROGRESS_ROLE, so a group can only show "
        "progress by inventing the fraction row 9a refuses"
    )


@pytest.mark.parametrize("row_height", [88, 96, 120, 160])
def test_the_format_control_never_covers_the_selector_line(
    qapp: QApplication, row_height: int
) -> None:
    """`T-136`: the third line ran underneath the control that sits beside it.

    **Two deliberate decisions collided**, and neither was wrong about its own half. `_paint_text`
    runs the selector at the *full* body width and says why — *"the control sits beside the first
    two lines, and nothing needs the third line's right-hand end"* — while `_control_rect` centred
    the control in the whole body. On a four-line row, centred is across line three. Measured on a
    96px row before the fix: `QRect(563, 35, 190, 26)` against `QRect(112, 57, 642, 34)`.

    **Several heights, because the collision is height-dependent.** One height and one font would
    have missed it, which is how it shipped: the overlap on a 96px row is 4px, and the maintainer
    saw it because a real row is taller and the selector wraps.

    The selector could not be the half that gave: narrowing it back to the leftover width beside
    the control is `T118-R8`, the defect where `REQ-009`'s selector was elided into uselessness.
    """
    delegate = RowDelegate()
    metrics = QFontMetrics(qapp.font())
    line = metrics.height()
    body = QRect(0, 0, RENDER_WIDTH, row_height).adjusted(PADDING, PADDING, -PADDING, -PADDING)

    control = delegate._control_rect(body, line)
    # Where `_paint_text` puts the selector: the last text line, at the full body width.
    selector = QRect(
        body.left() + THUMBNAIL_SIZE[0] + GAP,
        body.top() + (TEXT_LINES - 1) * line,
        max(body.right() - (body.left() + THUMBNAIL_SIZE[0] + GAP), 0),
        line * SELECTOR_LINES,
    )

    assert control.intersected(selector).isEmpty(), (
        f"on a {row_height}px row the control {control} covers the selector {selector}; the "
        "format selector REQ-009 promises the user can read is drawn underneath a combo box"
    )
    assert control.top() >= body.top(), "the control was pushed above the row"
    assert control.bottom() <= body.bottom(), "the control was pushed below the row"


def test_a_child_row_draws_two_lines_rather_than_being_sized_for_two(
    qapp: QApplication,
) -> None:
    """`UX-005` row 9c: an entry that has nothing to say draws two lines and is not clipped.

    `sizeHint` was shortened for an entry and the painter was not, so the selector line and the
    progress bar were drawn into space the row does not have and were **clipped** — the maintainer
    saw half a line of text under every entry of a playlist.

    Asserted as *the bar makes no difference*, which is the property. Comparing heights would pass
    against the clipped version, because the height was already right.

    **This used to assert that a format line made no difference either**, which was row 9c's
    unconditional form. `UX-005`'s 2026-08-05 amendment replaced it: an entry stays silent while it
    agrees with its group and speaks when it differs, because `T140-R3`'s group retarget makes
    divergence the guaranteed outcome on a part-done playlist. The silent case is still this one —
    the model answers an empty string — and the speaking case is asserted below.
    """
    common: dict[int, Any] = {
        HEADLINE_ROLE: "01 Prelude of Light",
        DETAIL_ROLE: "4:12 · 100% · 9.8 MB",
        PROGRESS_ROLE: 1.0,
        HUE_ROLE: 0,
        DEPTH_ROLE: 1,
    }
    without = paint_rows(RowsModel([common]), RowDelegate(), 0)
    silent = paint_rows(RowsModel([{**common, SELECTOR_ROLE: ""}]), RowDelegate(), 0)

    assert without == silent, (
        "an entry that agrees with its group drew something for its format anyway, which does not "
        "fit in the two lines row 9c gives it — so it is drawn clipped"
    )


def test_a_child_row_states_a_format_that_differs_from_its_group(qapp: QApplication) -> None:
    """`UX-005` amended 2026-08-05 (`T-157`): silence is conditional now, not unconditional.

    Retargeting a part-done playlist splits its formats by design — `T140-R3` moves every member
    that *can* move, and a finished track cannot — so the entries diverge and row 9c's premise,
    that an entry inherits its group's format, stops holding. An entry that differs says so.

    **The model decides whether there is something to say; the delegate decides how to draw it.**
    Here the model's answer is given directly, which is what makes this a test of the drawing.
    """
    common: dict[int, Any] = {
        HEADLINE_ROLE: "01 Prelude of Light",
        DETAIL_ROLE: "4:12 · 100% · 9.8 MB",
        HUE_ROLE: 0,
        DEPTH_ROLE: 1,
    }
    silent = RowsModel([{**common, SELECTOR_ROLE: ""}])
    speaking = RowsModel([{**common, SELECTOR_ROLE: "Download as: Audio only (original)"}])
    delegate = RowDelegate()

    assert paint_rows(silent, delegate, 0) != paint_rows(speaking, delegate, 0), (
        "an entry whose format differs from its group's drew nothing about it, so a retargeted "
        "playlist cannot say which row got which"
    )

    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, RENDER_WIDTH, ROW_HEIGHT)
    option.fontMetrics = QFontMetrics(option.font)
    quiet = delegate.sizeHint(option, silent.index(0, 0))
    loud = delegate.sizeHint(option, speaking.index(0, 0))
    assert loud.height() > quiet.height(), (
        f"a speaking entry is {loud.height()}px and a silent one {quiet.height()}px, so the line "
        "is drawn into space the row does not have and is clipped — the defect row 9c's own "
        "correction was about"
    )

    # And a top-level row still draws it, so this is not "the selector was removed for everyone".
    top = paint_rows(RowsModel([{**common, DEPTH_ROLE: 0}]), RowDelegate(), 0)
    top_with = paint_rows(
        RowsModel([{**common, DEPTH_ROLE: 0, SELECTOR_ROLE: "Format selector: bestaudio/best"}]),
        RowDelegate(),
        0,
    )
    assert top != top_with, "a top-level row stopped drawing its selector line as well"


def test_a_finished_segment_is_the_brand_rather_than_a_grey(qapp: QApplication) -> None:
    """`T-140`, corrected: sixteen done looked exactly like sixteen waiting.

    Every segment was drawn in `muted`, so the bar reported nothing while appearing to report
    something — the maintainer expected finished downloads to show as green and saw an empty
    track. `Highlight` is the theme's `primary`, which `T130-R1` deliberately kept there.

    **Colour is not the only signal** (`NFR-005`): the chip says `16 of 16` and the second line
    says `16 done`. This reinforces them, and the test asserts the *difference* rather than a
    particular colour, which would pin a palette choice.
    """
    common: dict[int, Any] = {HEADLINE_ROLE: "Trail Sounds", EXPANDED_ROLE: False, HUE_ROLE: 0}
    done = paint_rows(
        RowsModel([{**common, SEGMENTS_ROLE: [SegmentState.DONE] * 4}]), RowDelegate(), 0
    )
    waiting = paint_rows(
        RowsModel([{**common, SEGMENTS_ROLE: [SegmentState.WAITING] * 4}]), RowDelegate(), 0
    )

    assert done != waiting, (
        "a bar of four finished entries draws identically to four waiting ones, so it reports "
        "nothing while appearing to report something"
    )


def test_a_groups_bar_keeps_every_gap_at_every_width(qapp: QApplication) -> None:
    """`T-155`: sixteen entries must read as sixteen blocks, whatever the window's width.

    **The defect was arithmetic, and it looked intermittent.** Each block took its left edge from a
    rounded cumulative position and its width from a separately rounded span — two arithmetics for
    one geometry — so wherever the rounded width exceeded the real step a block ran into its
    neighbour and their gap vanished. Measured before the fix: 7 of 15 gaps lost at 600 px, 6 at
    617, 2 at 733, none at 800. Deterministic per width, which is why resizing seemed to fix and
    unfix it.

    **Swept rather than sampled**, because a single width is exactly what let this through: 800 px
    drew correctly and would have passed.

    **Painted through `_paint_segments` onto a bare image** rather than through a whole row: the
    claim is about the bar's geometry, and scanning a full row counts the thumbnail and the text as
    ink too.
    """
    states = [SegmentState.WAITING] * 16

    for width in (401, 600, 617, 733, 800, 1000):
        image = QImage(width, 8, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        try:
            RowDelegate()._paint_segments(
                painter,
                QRect(0, 0, width, 8),
                states,
                QColor("#666666"),
                QPalette(),
                # Every width here is above the merge threshold, so this stays a claim about the
                # one-block-per-entry rendering `T-155` fixed rather than about `T-164`'s.
                line_width=width,
            )
        finally:
            painter.end()

        inked = [image.pixelColor(x, 4).alpha() > 0 for x in range(width)]
        gaps = sum(1 for x in range(1, width) if inked[x - 1] and not inked[x])
        assert gaps == 15, (
            f"at {width}px the bar draws {gaps} gaps between blocks; sixteen entries need fifteen, "
            "and blocks that merge under-report a playlist to the user"
        )


def a_playlist(extra: dict[int, Any] | None = None) -> dict[int, Any]:
    """A group header carrying everything that competes for its last line (`T-163`, `T-167`).

    Verbs, a segmented bar and a format control at once, because the collisions this sweeps for
    only exist when all three are on the row — a group with no verbs cannot have them take the
    bar's width.

    `extra` is a dict for `a_row`'s reason: the roles are integers, and `**{ROLE: value}` is a
    `TypeError`.
    """
    row: dict[int, Any] = {
        HEADLINE_ROLE: "Trail Sounds",
        EXPANDED_ROLE: False,
        HUE_ROLE: 0,
        JOB_ID_ROLE: "playlist-1",
        VERBS_ROLE: [Verb.CANCEL_ALL, Verb.RETRY_FAILED],
        PRESET_CHOICES_ROLE: ["Best video available", "Audio only (MP3)"],
        SEGMENTS_ROLE: [SegmentState.DONE] * 4
        + [SegmentState.FAILED]
        + [SegmentState.WAITING] * 11,
    }
    row.update(extra or {})
    return row


def a_download(extra: dict[int, Any] | None = None) -> dict[int, Any]:
    """A running queue row: a plain fraction bar, and the verbs that were crowding it (`T-163`).

    `Open` and `Show in folder` are the pair the maintainer reported keeping their full width while
    the bar was squeezed to a stub, so they are the ones swept here.
    """
    row: dict[int, Any] = {
        HEADLINE_ROLE: "Ridgeline in 4K",
        DETAIL_ROLE: "412 MB of 640 MB",
        HUE_ROLE: 0,
        JOB_ID_ROLE: "job-1",
        PROGRESS_ROLE: 0.62,
        VERBS_ROLE: [Verb.OPEN, Verb.REVEAL, Verb.REMOVE],
        PRESET_CHOICES_ROLE: ["Best video available", "Audio only (MP3)"],
    }
    row.update(extra or {})
    return row


def bar_runs(row: dict[int, Any], width: int, delegate: RowDelegate | None = None) -> list[int]:
    """The widths of the ink runs on the row's progress bar, left to right.

    One run per block for a segmented bar, one run for a plain one, and `[]` when no bar was drawn
    at all — a real thing a narrow row does, and `T-163`'s defect rather than a measurement
    failure.

    **Read from the drawn row rather than from the delegate's arithmetic**, because the claim is
    about what a user sees as they drag the window edge. The scanline is the bar's own, and the
    count starts at the text line's left edge because the tile shares that scanline.
    """
    return bar_runs_in(
        paint_rows(RowsModel([row]), delegate or RowDelegate(), 0, width=width), row, width
    )


def bar_runs_in(image: QImage, row: dict[int, Any], width: int) -> list[int]:
    """`bar_runs`, reading a row already painted rather than painting one (`T168-R1`).

    Split out so a sweep that paints once per width can ask both questions of that paint — which
    verbs were dropped, and which rendering the bar chose. Repainting to answer the second would
    double the sweep and, worse, measure a second paint: the delegate records what it dropped on
    the *last* one.
    """
    # Held rather than inlined: a temporary `QStyleOptionViewItem` takes its `font` with it, and
    # `QFontMetrics` then reads a deleted C++ object.
    option = QStyleOptionViewItem()
    line = QFontMetrics(option.font).height()
    scanline = PADDING + 2 * line + 2 + BAR_HEIGHT // 2
    indent = TWISTY_WIDTH if EXPANDED_ROLE in row else 0
    first = PADDING + indent + THUMBNAIL_SIZE[0] + GAP
    runs: list[int] = []
    for x in range(first, width):
        if image.pixelColor(x, scanline).alpha() <= 0:
            continue
        if runs and image.pixelColor(x - 1, scanline).alpha() > 0:
            runs[-1] += 1
        else:
            runs.append(1)
    return runs


def bar_blocks(row: dict[int, Any], width: int) -> int:
    """How many blocks the row's bar draws at `width`. `0` when it drew none."""
    return len(bar_runs(row, width))


def test_the_bar_changes_shape_at_most_once_across_a_drag(qapp: QApplication) -> None:
    """`T-167`: narrowing the window merged the blocks, and narrowing it further un-merged them.

    **The input was wrong, not the threshold.** The rendering was chosen from the space left over
    after the verbs, and the verbs' width is not monotonic in the window's — at the moment one
    drops into `⋯` (`T-135`) the leftover *grows*. Measured on this row before the fix, the bar's
    own width ran 76 px at a 440 px window, 12 px at 460, 32 px at 480 and 9 px at 500, so the
    rendering reversed twice while the user dragged one edge one way.

    **Swept one pixel at a time, and in both directions by construction.** The rendering is a pure
    function of the width — nothing about it is carried between paints — so a single transition
    across the sweep is exactly the property that no drag direction can reverse it, and that it
    un-merges at the width it merged at rather than at a second one.

    **Widths where the row draws no bar at all are left out, and that is deliberate.** They exist:
    the verbs take their full width and can leave the bar nothing, which is `T-163`, a different
    defect with its own criterion and its own test. Asserting it here would make this test fail for
    a reason it is not about. The guard below is what stops that exclusion from emptying the sweep.
    """
    row = a_playlist()
    measured = [(width, bar_blocks(row, width)) for width in SWEEP_WIDTHS]
    drawn = [(width, blocks) for width, blocks in measured if blocks]

    assert len(drawn) > len(SWEEP_WIDTHS) // 2, (
        f"the row drew a bar at only {len(drawn)} of {len(SWEEP_WIDTHS)} widths, so this sweep is "
        "not measuring a rendering often enough to say anything about how often it changes"
    )

    changes = [
        (width, before, after) for (_, before), (width, after) in pairwise(drawn) if before != after
    ]

    assert len(changes) <= 1, (
        f"the bar takes {len({blocks for _, blocks in drawn})} shapes across "
        f"{SWEEP_WIDTHS[0]}-{SWEEP_WIDTHS[-1]}px, changing at "
        f"{[width for width, _, _ in changes]}; a user dragging one edge steadily sees it change, "
        "change back and change again"
    )


def test_a_narrow_bar_merges_to_a_fixed_count_rather_than_thinner_blocks(
    qapp: QApplication,
) -> None:
    """`T-164` and `UX-005` row 9b-i: what the bar draws once its entries no longer each fit.

    Sixteen blocks in a 200 px bar are twelve pixels each and read as noise. The maintainer's first
    suggestion — one solid *done of total* bar — was **rejected**, because a solid bar cannot show
    that one of the four finished entries failed, which is the whole of row 9b. So the entries
    merge into a fixed count instead, and the two renderings are the only two there are.
    """
    row = a_playlist()
    drawn = [(width, bar_blocks(row, width)) for width in SWEEP_WIDTHS]
    drawn = [(width, blocks) for width, blocks in drawn if blocks]

    assert {blocks for _, blocks in drawn} == {MERGED_BLOCKS, 16}, (
        f"the bar draws {sorted({blocks for _, blocks in drawn})} blocks across the sweep; row "
        f"9b-i has exactly two renderings, one per entry and a merged {MERGED_BLOCKS}"
    )
    narrow = [width for width, blocks in drawn if blocks == MERGED_BLOCKS]
    wide = [width for width, blocks in drawn if blocks == 16]
    assert max(narrow) < min(wide), (
        "the merged rendering is not confined to the narrow end, so it is not the narrow window "
        "that decides it"
    )


def test_the_merge_threshold_is_the_stated_block_minimum(qapp: QApplication) -> None:
    """`T-164`: the threshold is derived from a minimum legible block width, not tuned by eye.

    **Asserted at its own boundary rather than sampled either side of it.** One pixel decides it,
    and a test that checked 400 px and 900 px would pass for a threshold anywhere between them.
    """
    assert segment_blocks(16, segment_span(16)) == 16, (
        "a line exactly wide enough for sixteen legible blocks does not draw them, so the "
        "threshold is not the one MIN_BLOCK_WIDTH states"
    )
    assert segment_blocks(16, segment_span(16) - 1) == MERGED_BLOCKS, (
        "one pixel below the stated minimum the bar still draws one block per entry, which is the "
        "twelve-pixel noise T-164 exists to stop"
    )
    assert segment_blocks(MERGED_BLOCKS, 0) == MERGED_BLOCKS, (
        "a playlist with no more entries than the merged count invents blocks by merging"
    )


def test_a_failed_entry_stays_visible_at_every_width(qapp: QApplication) -> None:
    """`UX-005` row 9b's guarantee, which is what merging had to keep (`T-164`).

    **A covered failure must not be outvoted by three successes.** Two playlists identical but for
    one entry — waiting in the first, failed in the second — must never draw the same row. Under a
    merged block that covers two entries, taking the *worst* is what keeps them apart; taking the
    commonest or the first would collapse them at exactly the widths the merge exists for.

    **The failed entry is deliberately not the first of its merged block.** Written with it at
    index 4 this test passed against a fold that took each block's *first* state, because that
    happened to be the failure — the rule was never exercised. At index 5 the block covers a
    waiting entry and then the failure, so only taking the worst keeps the two rows apart.
    `test_a_merged_block_takes_the_worst_state_it_covers` checks the remaining positions directly,
    which is cheaper than sweeping sixteen of these.

    Widths drawing no bar at all are excluded for `T-163`'s reason, and the guard is that they are
    the minority.
    """
    healthy = a_playlist({SEGMENTS_ROLE: [SegmentState.DONE] * 4 + [SegmentState.WAITING] * 12})
    broken = a_playlist(
        {
            SEGMENTS_ROLE: [SegmentState.DONE] * 4
            + [SegmentState.WAITING]
            + [SegmentState.FAILED]
            + [SegmentState.WAITING] * 10
        }
    )

    compared = 0
    for width in SWEEP_WIDTHS:
        if not bar_blocks(healthy, width):
            continue
        compared += 1
        fine = paint_rows(RowsModel([healthy]), RowDelegate(), 0, width=width)
        failed = paint_rows(RowsModel([broken]), RowDelegate(), 0, width=width)
        assert fine != failed, (
            f"at {width}px a playlist that skipped a track draws exactly like one that got "
            "everything, which is the lie row 9b exists to prevent"
        )

    assert compared > len(SWEEP_WIDTHS) // 2, (
        f"only {compared} of {len(SWEEP_WIDTHS)} widths drew a bar to compare"
    )


def test_a_playlists_blocks_keep_their_width_and_the_verbs_give_way(
    qapp: QApplication,
) -> None:
    """`T-163`: the verbs held their ground until the progress bar had none.

    What decided "fit" was the verbs' own width against the space left over, and the bar was not in
    that calculation — so the verbs took what they needed and the bar took the remainder, which at
    a narrow window was a stub. `T-135` already built the mechanism for the other answer: a dropped
    verb is still reachable through `⋯` and through the context menu, and there is no overflow menu
    for *progress*.

    **The stated floor, and where it stops applying.** Blocks stay at `MIN_BLOCK_WIDTH` until the
    line cannot hold even the merged bar beside the `⋯`. Past that the button wins, because a row
    that kept its bar and dropped the button would leave the pointer no route to its verbs at all —
    so the assertion is the rule, not an absolute: a bar under its minimum is only allowed on a row
    that has already given up every verb it has.
    """
    row = a_playlist()
    for width in SWEEP_WIDTHS:
        delegate = RowDelegate()
        runs = bar_runs(row, width, delegate)
        assert runs, (
            f"at {width}px the verbs took the whole line and the row draws no progress at all, "
            "which is the row's only answer to how far along a playlist is"
        )
        if min(runs) < MIN_BLOCK_WIDTH:
            assert set(delegate.overflowing("playlist-1")) == set(row[VERBS_ROLE]), (
                f"at {width}px a block is {min(runs)}px while a verb is still drawn beside it; "
                "the verbs are the half that can give and they have not given"
            )


def test_a_downloads_bar_keeps_its_minimum_and_the_verbs_give_way(
    qapp: QApplication,
) -> None:
    """`T-163` on a plain fraction bar, which is the row the maintainer reported.

    `Open` and `Show in folder` kept their full width while the bar was squeezed to nothing. Its
    minimum is smaller than a sixteen-entry bar's, because it has one position to show rather than
    sixteen endings — that difference is the criterion's "derived from what it has to show".
    """
    row = a_download()
    for width in SWEEP_WIDTHS:
        delegate = RowDelegate()
        runs = bar_runs(row, width, delegate)
        assert runs, f"at {width}px the verbs took the whole line and the bar was not drawn"
        if sum(runs) < MIN_FRACTION_BAR:
            assert set(delegate.overflowing("job-1")) == set(row[VERBS_ROLE]), (
                f"at {width}px the bar is {sum(runs)}px, under the stated {MIN_FRACTION_BAR}, "
                "while a verb is still drawn beside it"
            )


#: The entry counts the reserve is swept at (`T168-R1`).
#:
#: **Both sides of `MERGED_BLOCKS`, and four different merge thresholds above it.** The criterion
#: is *"for a row of any entry count"*, and a sweep fixed at sixteen proves it for sixteen: a
#: reserve that asked `segment_blocks` for every other count would leave the named gate green.
#: `segment_span` is `17n - 1`, so each count above the merge threshold crosses at its own width —
#: 152 px at nine, 271 at sixteen, 407 at twenty-four, 628 at thirty-seven — and a restoration
#: keyed to any one of them is caught by the others.
#:
#: **Five and eight are not filler.** At or below `MERGED_BLOCKS` there is no merge and therefore
#: no step to fall off, so they assert that the property holds where the defect could not occur —
#: which is what stops a "fix" that merely special-cases the merging counts.
#:
#: Sixty is deliberately absent: `segment_span(60)` is 1019 px, wider than any bar this sweep can
#: give, so it never draws its unmerged rendering and could not cross anything.
#:
#: **Measured against both mutants, and nine kills neither.** Restoring
#: `segment_span(segment_blocks(entries, room))` fails at 16, 24 and 37; restoring it everywhere
#: *except* sixteen — the count-specific form `T168-R1` names — fails at 24 and 37. Nine survives
#: both, because its step is `segment_span(9) - segment_span(8)`, 17 px, and no verb is that
#: narrow: the old reserve is harmless just above the threshold and the gap it hands back only
#: becomes a button further up. It stays for what it does assert — that the property holds at a
#: count that merges — and the counts that kill the mutants are 24 and 37.
RESERVE_COUNTS: Final = (5, 8, 9, 16, 24, 37)


@pytest.mark.parametrize("entries", RESERVE_COUNTS)
def test_a_verb_dropped_at_one_width_never_returns_at_a_narrower_one(
    qapp: QApplication,
    entries: int,
) -> None:
    """`T-168`: the maintainer narrowed the window and `Remove` came back.

    Measured before the fix, on a sixteen-entry playlist: the button was drawn at 560 px, gone at
    496 px, **drawn again at 432 px**, and gone at 360 px. Nothing was unreachable — `⋯` held it
    throughout — but a control that returns when you take space away teaches the user that the row
    is arbitrary.

    **`T-163` and `T-164` are each right and their composition was not.** The verbs yield to the
    bar, and a narrow bar merges sixteen blocks into eight; so the bar's demand was a step function
    of the width, and the step was bigger than a button. Crossing the merge threshold handed the
    verbs 136 px back — `segment_span(16)` is 271 px and `segment_span(8)` is 135 px — which is
    exactly enough to fit a verb that had just been dropped.

    **Swept rather than sampled.** The step is one threshold wide; a test checking three chosen
    widths passes straight over it, which is how the defect survived `T-167`'s own monotonicity
    claim. `SWEEP_WIDTHS` is every pixel from 300 to 1200, and the assertion is on the *shape* of
    the sequence — the dropped set only ever grows as the row narrows — rather than on any width's
    value, so it keeps holding when a font or a label changes.

    **Swept at every count in `RESERVE_COUNTS`, not only at sixteen** (`T168-R1`). The criterion
    this test exists for says *any* entry count, and the reproduced defect was sixteen; a sweep
    pinned there stays green for a reserve that consults `segment_blocks` — the rejected
    mechanism — at every other count. Each count also asserts which renderings its own sweep
    produced, so a count whose merge threshold has moved outside the swept range fails loudly
    instead of quietly proving nothing.
    """
    row = a_playlist({SEGMENTS_ROLE: [SegmentState.DONE] * entries})
    delegate = RowDelegate()
    previous: frozenset[Verb] | None = None
    previous_width = 0
    renderings: set[int] = set()

    for width in reversed(SWEEP_WIDTHS):
        image = paint_rows(RowsModel([row]), delegate, 0, width=width)
        blocks = len(bar_runs_in(image, row, width))
        if blocks:
            renderings.add(blocks)
        dropped = frozenset(delegate.overflowing("playlist-1"))
        if previous is not None:
            returned = previous - dropped
            assert not returned, (
                f"{sorted(v.value for v in returned)} was in the overflow at {previous_width}px "
                f"and is drawn again at {width}px on a {entries}-entry row — narrowing the row "
                "gave a verb back. The bar merges at this threshold and hands the verbs more "
                "space than it took"
            )
        previous, previous_width = dropped, width

    assert previous, (
        f"at the narrowest swept width a {entries}-entry row still draws every verb, so this "
        "never exercised the crowding it exists to check"
    )

    if entries > MERGED_BLOCKS:
        assert renderings == {MERGED_BLOCKS, entries}, (
            f"a {entries}-entry row draws {sorted(renderings)} across the sweep; it must span "
            f"this count's own merge threshold — {segment_span(entries)}px of bar — or it never "
            "reaches the step the reserve exists to flatten"
        )
    else:
        assert renderings == {entries}, (
            f"a {entries}-entry row draws {sorted(renderings)} across the sweep; at or below "
            f"{MERGED_BLOCKS} entries there is no merged rendering to reach, which is why these "
            "counts hold the property where the defect could not occur"
        )


def test_the_overflow_still_holds_exactly_what_the_row_dropped(qapp: QApplication) -> None:
    """`T-135`, re-asserted because `T-163` changed what makes a verb drop.

    A verb is now dropped for crowding the bar as well as for running off the row. The menu must
    still hold exactly what the row could not show — not one fewer, and nothing it did show.
    """
    row = a_download()
    dropped_somewhere = False
    for width in SWEEP_WIDTHS:
        delegate = RowDelegate()
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, width, ROW_HEIGHT)
        option.fontMetrics = QFontMetrics(option.font)
        model = RowsModel([row])
        paint_rows(model, delegate, 0, width=width)

        body, area = delegate._verb_area(option, model.index(0, 0))
        drawn = {
            verb
            for verb, _ in delegate._verb_rects(
                QFontMetrics(option.font), area, body, model.index(0, 0)
            )
            if verb is not None
        }
        dropped = set(delegate.overflowing("job-1"))
        dropped_somewhere = dropped_somewhere or bool(dropped)

        assert drawn | dropped == set(row[VERBS_ROLE]), (
            f"at {width}px the row shows {sorted(drawn)} and the menu offers {sorted(dropped)}, "
            f"which is not the {sorted(row[VERBS_ROLE])} the model offered"
        )
        assert not drawn & dropped, (
            f"at {width}px the menu repeats {sorted(drawn & dropped)}, which the row already shows"
        )

    assert dropped_somewhere, (
        "no width in the sweep dropped a verb, so this proves nothing about the overflow"
    )


#: What a playlist header says it will download as (`UX-005` row 13). Long enough that a narrowed
#: line loses words rather than a character — the maintainer saw this drawn as `Download`.
FORMAT_LINE: Final = "Download as: Best video available"


def format_line(row: dict[int, Any], width: int) -> QImage:
    """Just the row's format line, cropped out of the painted row (`T-166`).

    The band is line three of four, which is where `_paint_text` puts the selector and is a whole
    line above the verbs. Cropping rather than scanning because the claim is that the line is drawn
    *identically*, and comparing images says that exactly.
    """
    option = QStyleOptionViewItem()
    line = QFontMetrics(option.font).height()
    # **What `sizeHint` gives a row that draws all four of its lines.** Painted at `ROW_HEIGHT`
    # instead, the last line is squeezed into whatever pixels remain — a fair rendering of a row
    # with nothing on line three and a misleading one of a row carrying a format line.
    height = TEXT_LINES * line + 2 * PADDING
    image = paint_rows(RowsModel([row]), RowDelegate(), 0, width=width, height=height)
    return image.copy(QRect(0, PADDING + 2 * line, width, line))


def test_the_verbs_do_not_narrow_the_format_line_above_them(qapp: QApplication) -> None:
    """`T-166`: `Download as: Best video available` became `Download` as the window narrowed.

    **The verbs were spending the same width twice.** They are laid out on the last line, and
    `_paint_text` already gives them that line by dropping the selector to a single line above it —
    and then it also stopped the selector's *width* at the leftmost button, which sits a whole line
    below. So as the window narrowed the buttons advanced leftward across a line they do not
    occupy, until the format line was a stump.

    **Asserted as: the verbs change nothing about the line above them.** The same row with and
    without verbs must draw that line identically at every width. That is stronger than measuring
    how much of it survives, and it cannot pass by both rows being equally truncated — the row
    without verbs is not narrowed by anything.

    `T118-R8` is the rule underneath: the selector is the half that cannot give, because a
    truncated format is one the user can neither read nor copy, and there is no overflow menu for a
    sentence. The verbs have one, and `T-163` is where they use it.
    """
    with_verbs = a_playlist({SELECTOR_ROLE: FORMAT_LINE})
    without_verbs = a_playlist({SELECTOR_ROLE: FORMAT_LINE, VERBS_ROLE: []})

    inked = 0
    for width in SWEEP_WIDTHS:
        crowded = format_line(with_verbs, width)
        alone = format_line(without_verbs, width)
        inked += crowded != format_line(a_playlist({VERBS_ROLE: []}), width)
        assert crowded == alone, (
            f"at {width}px the format line is drawn differently once the row has verbs, so the "
            "buttons on the line below are taking width from the line above them"
        )

    assert inked > len(SWEEP_WIDTHS) // 2, (
        f"the format line drew nothing at {len(SWEEP_WIDTHS) - inked} of {len(SWEEP_WIDTHS)} "
        "widths, so comparing it proves little"
    )


def a_staging_row(extra: dict[int, Any] | None = None) -> dict[int, Any]:
    """An add-dialog row: the tile, the control and the selector all present at once (`T-160`).

    No verbs and no job behind it, which is what a staged row is — and the surface the maintainer
    found this on, at the size the dialog opens at.
    """
    return a_row(
        0,
        extra={
            SELECTOR_ROLE: FORMAT_LINE,
            PRESET_ROLE: "Best video available",
            PRESET_CHOICES_ROLE: ["Best video available", "Audio only (MP3)"],
            **(extra or {}),
        },
    )


def test_the_format_control_never_covers_the_thumbnail(qapp: QApplication) -> None:
    """`T-160`, and checklist row 2.7's property, inherited 2026-08-05.

    The control was anchored to the right edge and clamped to `body.left()`, with nothing between
    it and the picture — so on a row narrower than roughly 300 px *Same as all* was drawn across
    the thumbnail. `EDITOR_WIDTH` is 190 and the tile is 96 plus a 10 px gap, which is where that
    number comes from.

    **All three surfaces, because `_control_rect` is shared** and this was reported on the add
    dialog and then confirmed on a queue row the same day. A playlist header is included because
    its body is indented by the disclosure, which is exactly the arithmetic that used to differ
    between the paint and the click.

    **Swept, and asserted as geometry**: one width is what let `T-155` through.
    """
    for name, row in (
        ("staging row", a_staging_row()),
        ("queue row", a_download()),
        ("playlist header", a_playlist({SELECTOR_ROLE: FORMAT_LINE})),
    ):
        delegate = RowDelegate()
        model = RowsModel([row])
        for width in SWEEP_WIDTHS:
            option = QStyleOptionViewItem()
            option.rect = QRect(0, 0, width, ROW_HEIGHT)
            option.fontMetrics = QFontMetrics(option.font)
            index = model.index(0, 0)

            body, size = delegate._body_of(option, index)
            tile = QRect(body.left(), body.top(), *size)
            control = delegate._control_of(option, index)

            assert control.intersected(tile).isEmpty(), (
                f"on a {width}px {name} the control {control} is drawn over the thumbnail {tile}"
            )
            assert control.width() >= MIN_CONTROL_WIDTH, (
                f"on a {width}px {name} the control is {control.width()}px, under the stated "
                f"{MIN_CONTROL_WIDTH}; it narrows to that and no further, and is never withheld"
            )
            assert control.right() <= body.right(), (
                f"on a {width}px {name} the control runs off the row's right edge"
            )


@pytest.mark.parametrize("tile", [THUMBNAIL_SIZE[0], CHILD_THUMBNAIL[0]])
def test_the_control_stays_clear_of_the_tile_at_any_body_width(
    qapp: QApplication, tile: int
) -> None:
    """`T-160`, below the widths a window reaches, and for a child row's smaller picture.

    **The clamp is the guarantee; the text minimum is only what usually keeps them apart.**
    Subtracting `MIN_TEXT_WIDTH` happens to hold the control clear of a 96 px tile down to about a
    186 px row, which is narrower than the swept range — so without this the clamp would be
    untested code that two unrelated constants were standing in for. Here the body is driven down
    until only the clamp can be doing the work.

    A child's tile is smaller and its body is indented, so the two sizes are checked rather than
    assuming the full one is the harder case.
    """
    delegate = RowDelegate()
    option = QStyleOptionViewItem()
    line = QFontMetrics(option.font).height()

    for body_width in range(60, 500):
        body = QRect(PADDING, PADDING, body_width, ROW_HEIGHT - 2 * PADDING)
        picture = QRect(body.left(), body.top(), tile, tile)
        control = delegate._control_rect(body, line, tile=tile)
        assert control.intersected(picture).isEmpty(), (
            f"with a {body_width}px body and a {tile}px tile the control {control} is drawn over "
            f"the picture {picture}"
        )


def test_the_thumbnail_is_drawn_the_same_with_a_control_and_without(
    qapp: QApplication,
) -> None:
    """`T-160` from the pixels, which is where the maintainer saw it.

    The geometry above says the rectangles do not meet; this says nothing was painted over the
    picture, which is the claim a user could check. The row with no choices draws no control at
    all, so its tile is what an uncovered one looks like.
    """
    covered = a_download()
    bare = a_download({PRESET_CHOICES_ROLE: None})
    tile = QRect(PADDING, PADDING, *THUMBNAIL_SIZE)

    for width in SWEEP_WIDTHS:
        with_control = paint_rows(RowsModel([covered]), RowDelegate(), 0, width=width)
        without = paint_rows(RowsModel([bare]), RowDelegate(), 0, width=width)
        assert with_control.copy(tile) == without.copy(tile), (
            f"at {width}px the row's picture is drawn differently once the row has a format "
            "control, so the control is being painted over the thumbnail"
        )


def test_the_minimum_row_width_is_where_the_control_stops_narrowing(
    qapp: QApplication,
) -> None:
    """`T-150`: the derived width and the delegate's own behaviour, pinned to each other.

    **This is the test the criterion asks for when it says one must fail if the two stop
    agreeing.** `minimum_row_width` states the arithmetic; `_control_rect` runs it. A width derived
    from constants that no longer describe the drawing is exactly the stale number the criterion
    rules out, and only asserting the boundary catches it — either side of it, both agree.
    """
    delegate = RowDelegate()
    option = QStyleOptionViewItem()
    line = QFontMetrics(option.font).height()
    width = minimum_row_width(QFontMetrics(option.font))

    def control_at(row_width: int) -> int:
        body = QRect(0, 0, row_width, ROW_HEIGHT).adjusted(PADDING, PADDING, -PADDING, -PADDING)
        return delegate._control_rect(body, line).width()

    assert control_at(width) == EDITOR_WIDTH, (
        f"at the derived minimum of {width}px the control is {control_at(width)}px, not the full "
        f"{EDITOR_WIDTH}; the number and the drawing disagree"
    )
    assert control_at(width - 1) < EDITOR_WIDTH, (
        f"the control is still full width one pixel below the derived minimum, so {width} is not "
        "the boundary it claims to be and a narrower window would do"
    )


def test_the_minimum_row_width_is_where_the_selector_stops_fitting(
    qapp: QApplication,
) -> None:
    """`T-150`: the same pinning for the half a preset catalogue decides.

    `selector_line_width` searches with `SELECTOR_FLAGS`, which is the value `_paint_text` lays the
    line out with — measured and drawn through one definition, so the width cannot be computed for
    a wrapping the row does not use.
    """
    # Held, not inlined: a temporary option takes its `font` with it (see `bar_runs`).
    option = QStyleOptionViewItem()
    metrics = QFontMetrics(option.font)
    # Long enough to need both lines and to be the binding constraint, rather than the anatomy.
    text = (
        "Download as: Best video up to 1080p (MP4) — this row only · Format selector: "
        "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]"
    )
    width = minimum_row_width(metrics, [text])

    def lines_at(row_width: int) -> int:
        body = QRect(0, 0, row_width, ROW_HEIGHT).adjusted(PADDING, PADDING, -PADDING, -PADDING)
        available = body.right() - (body.left() + THUMBNAIL_SIZE[0] + GAP)
        drawn = metrics.boundingRect(QRect(0, 0, available, 1 << 20), SELECTOR_FLAGS, text)
        return round(drawn.height() / metrics.height())

    assert width > minimum_row_width(metrics), (
        "this selector is not the binding constraint, so the test is measuring the anatomy again"
    )
    assert lines_at(width) <= SELECTOR_LINES, (
        f"at the derived minimum of {width}px the selector still takes {lines_at(width)} lines, "
        f"and the row draws {SELECTOR_LINES}"
    )
    assert lines_at(width - 1) > SELECTOR_LINES, (
        f"the selector still fits one pixel below {width}, so that is not the boundary"
    )


def test_a_merged_block_takes_the_worst_state_it_covers() -> None:
    """`UX-005` row 9b-i, at every position a failure can occupy.

    The swept test above can only afford one position; this covers the rest, and it is the one
    that fails when the fold takes a block's first, commonest or last state instead of its worst.

    **Below the two endings the order is least-advanced first**, so a block never claims more
    progress than the slowest entry under it. Over-reporting is the lie a merged bar is most able
    to tell: a block covering one finished entry and one still queued that read *done* would let a
    half-finished playlist draw itself complete.
    """
    for position in range(16):
        states = [SegmentState.DONE] * 16
        states[position] = SegmentState.FAILED
        assert SegmentState.FAILED in _merge(states, MERGED_BLOCKS), (
            f"a failure at entry {position} vanishes when the bar merges, so a playlist that "
            "skipped a track draws like one that got everything"
        )

    assert _merge([SegmentState.DONE, SegmentState.WAITING], 1) == (SegmentState.WAITING,), (
        "a block covering a finished entry and a queued one reports the finished one, so a "
        "half-done playlist can draw itself as complete"
    )
    assert _merge([SegmentState.CANCELLED, SegmentState.FAILED], 1) == (SegmentState.FAILED,), (
        "a failure is outranked by an abandonment, so the entry a user must act on is the one "
        "that disappears"
    )


def test_an_abandoned_block_is_not_drawn_like_a_finished_one(qapp: QApplication) -> None:
    """`T-165`, in **both** themes.

    Done was the brand green and failed was the ink at alpha 170 — two solid dark fills, so a
    playlist where every entry was cancelled drew a bar that looked exactly as full as one where
    every entry succeeded, and *full* is the shape the eye reads as finished. Checklist row 3.6
    only ever asked that failed differ from **queued**, and those did differ, by opacity; the pair
    a user confuses is finished against abandoned.

    **Both themes, because the fix reads a semantic colour** rather than nudging an alpha. A hex
    that separates the three on the light theme can collapse two of them on the dark one, and the
    dark theme is the one nobody has looked at yet (`docs/CRITERION_8_CHECKLIST.md` §5).

    Sampled from the middle of each block, one state per render, so nothing here depends on how
    the blocks are laid out — that is `T-155`'s question and it has its own test.

    **The palette here is a list's, not the application's, and that is the point.** This test first
    built `theme.palette(dressing)` and passed — while the window drew a completed playlist as
    sixteen blank blocks. A style sheet's `selection-background-color` is propagated by Qt into the
    styled widget's palette, and `T130-R1` scopes the quiet tint to `QListView` deliberately, so
    the palette a `RowDelegate` is handed answers `#ebf1ee` for `Highlight` where the application's
    answers `#1e5e47`. Building the palette from the theme skipped the one step that made the
    colour wrong. Measured on the built window and reproduced here, so *done* must now come from
    somewhere a selection tint cannot reach.
    """
    from tracks_and_trails.ui import theme

    for dressing in (theme.LIGHT, theme.DARK):
        theme.apply(qapp, dressing)
        palette = theme.palette(dressing)
        palette.setColor(QPalette.ColorRole.Highlight, QColor(dressing.selection))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(dressing.on_selection))
        drawn: dict[SegmentState, str] = {}
        for state in SegmentState:
            image = QImage(40, 8, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.white)
            painter = QPainter(image)
            try:
                RowDelegate()._paint_segments(
                    painter,
                    QRect(0, 0, 40, 8),
                    [state],
                    QColor(dressing.muted),
                    palette,
                    line_width=40,
                )
            finally:
                painter.end()
            drawn[state] = image.pixelColor(20, 4).name()

        assert drawn[SegmentState.DONE] == QColor(dressing.primary).name(), (
            f"on the {dressing.name} theme a finished block draws {drawn[SegmentState.DONE]}, not "
            f"the brand {dressing.primary}. A list's palette carries the selection tint in "
            "Highlight, so reading the brand from there draws the tint — which on the light theme "
            "is a near-white fill against a white row, and no fill at all to a user"
        )
        assert drawn[SegmentState.DONE] != drawn[SegmentState.WAITING], (
            f"on the {dressing.name} theme a finished block and a waiting one both draw "
            f"{drawn[SegmentState.DONE]}, which is what `T-140` was corrected for"
        )
        assert drawn[SegmentState.DONE] != drawn[SegmentState.FAILED], (
            f"on the {dressing.name} theme a failed block is {drawn[SegmentState.FAILED]} and a "
            f"finished one is {drawn[SegmentState.DONE]}"
        )
        assert drawn[SegmentState.DONE] != drawn[SegmentState.CANCELLED], (
            f"on the {dressing.name} theme a cancelled block is "
            f"{drawn[SegmentState.CANCELLED]} and a finished one is {drawn[SegmentState.DONE]}; "
            "a wholly cancelled playlist must not draw the bar a wholly finished one draws"
        )
        assert drawn[SegmentState.CANCELLED] != drawn[SegmentState.FAILED], (
            f"on the {dressing.name} theme cancelled and failed both draw "
            f"{drawn[SegmentState.CANCELLED]}; the words separate them and the bar must too"
        )

    theme.apply(qapp, theme.LIGHT)


def test_a_child_rows_picture_stays_inside_its_smaller_slot(
    qapp: QApplication, stores: Callable[..., ThumbnailStore]
) -> None:
    """`T-154`: `UX-005` row 9c gives an entry a smaller tile, and the picture must respect it.

    **The painter took the pixmap's size and centred that on the tile.** `ThumbnailStore` caches at
    `THUMBNAIL_SIZE` — 96x54, and the square fixture scales to 54x54 — while a child's slot is
    38x22. So a parent row looked correct and a child drew the picture over its own title.

    **Differential, against the same row without a picture.** The row's text is ink outside the tile
    and always has been, so "is anything drawn there" cannot be the question; "does the picture
    change anything there" can.

    **And it asserts the picture actually arrived.** Comparing two renders that are both the
    derived placeholder would pass while proving nothing — the vacuous shape this project keeps
    finding — so the tile itself must differ before the area outside it is allowed to match.

    **This does not kill the mutant, and that is disclosed rather than papered over.** Restoring
    `target.setSize(pixmap.size())` leaves this green, because at a device pixel ratio of 1 —
    which `offscreen` always is — the cached pixmap's `size()` and the slot coincide and nothing
    overflows. The window that showed the defect was not at 1. So this guards the property on
    every platform and reproduces the reported failure on none of them; the fix is verified by the
    geometry it now computes, not by this test failing without it.
    """
    loader = FakeLoader(IMAGE_SOURCE.read_bytes())
    store = stores(loader=loader)
    delegate = RowDelegate(thumbnails=store)

    bare = a_row(0, thumbnail=None)
    bare[DEPTH_ROLE] = 1
    without = paint_rows(RowsModel([bare]), delegate, 0)

    pictured = a_row(0, thumbnail="https://pics.invalid/child.jpg")
    pictured[DEPTH_ROLE] = 1
    model = RowsModel([pictured])
    paint_rows(model, delegate, 0)
    assert spin_until(qapp, lambda: store.pixmap("https://pics.invalid/child.jpg") is not None)
    with_picture = paint_rows(model, delegate, 0)

    # The slot a child's tile occupies: indented by its depth, `CHILD_THUMBNAIL` in size.
    slot = QRect(INDENT + PADDING, 0, CHILD_THUMBNAIL[0], with_picture.height())

    inside = [
        (x, y)
        for x in range(slot.left(), slot.right() + 1)
        for y in range(with_picture.height())
        if with_picture.pixelColor(x, y) != without.pixelColor(x, y)
    ]
    assert inside, (
        "the two renders are identical inside the tile, so no picture was drawn and this would "
        "pass without testing anything"
    )

    outside = [
        (x, y)
        for x in range(with_picture.width())
        for y in range(with_picture.height())
        if not (slot.left() <= x <= slot.right())
        and with_picture.pixelColor(x, y) != without.pixelColor(x, y)
    ]
    assert not outside, (
        f"the picture changes {len(outside)} pixels outside its {CHILD_THUMBNAIL[0]}px slot, the "
        f"first at {outside[0]}; it is drawn at its own size rather than the slot's and covers the "
        "row's title"
    )


def test_every_role_has_its_own_number() -> None:
    """Two roles sharing an offset is silent until something reads the wrong data.

    **Found by doing it.** `PRESET_PLACEHOLDER_ROLE` was added at `UserRole + 16`, which
    `SEGMENTS_ROLE` already held, so the group's format control asked for its placeholder and was
    handed a list of segment states. Nothing raised: `data()` answers whatever the first matching
    branch returns, and both are `Any`.

    Derived from the module rather than listed here, so a role added tomorrow is covered the day it
    appears — `ai/TESTING.md` §13's rule about a test that transcribes rather than re-derives does
    not apply, because the property *is* "no two of them agree" rather than a specification the
    test should hold independently.
    """
    roles = {
        name: value
        for name, value in vars(row_delegate).items()
        if name.endswith("_ROLE") and isinstance(value, int)
    }
    by_number: dict[int, list[str]] = {}
    for name, value in roles.items():
        by_number.setdefault(value, []).append(name)

    collisions = {value: names for value, names in by_number.items() if len(names) > 1}
    assert not collisions, (
        f"roles sharing a number: {collisions}. Whichever branch of `data()` is tested first wins, "
        "so the loser silently returns the other's value"
    )


# --- T-224: the `⋮` zone is drawn as a button ------------------------------------------------


def _zone_pixels(image: QImage, zone: QRect) -> list[int]:
    """Every pixel inside `zone`, so two paints can be compared where the change should be."""
    return [
        image.pixel(x, y)
        for y in range(zone.top(), min(zone.bottom() + 1, image.height()))
        for x in range(zone.left(), min(zone.right() + 1, image.width()))
    ]


def _selectable_row_option(width: int = RENDER_WIDTH) -> QStyleOptionViewItem:
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, width, ROW_HEIGHT)
    option.fontMetrics = QFontMetrics(option.font)
    return option


def _row_with_a_control() -> RowsModel:
    """A row the delegate will actually draw a control on.

    `_editable` gates the whole control paint on `PRESET_CHOICES_ROLE`, so a row without choices
    draws no combo and therefore no `⋮` zone — and a zone test on such a row asserts against an
    empty rectangle. The first draft of these tests did exactly that and one of them passed on ink
    belonging to the row behind.
    """
    return RowsModel(
        [
            {
                HEADLINE_ROLE: "A video",
                DETAIL_ROLE: "",
                STATE_ROLE: "",
                HUE_ROLE: 0,
                PRESET_CHOICES_ROLE: ("Best video available", "Audio only (MP3)"),
                PRESET_ROLE: "Best video available",
            }
        ]
    )


def test_the_menu_zone_is_drawn_as_a_button_not_bare_punctuation(qapp: QApplication) -> None:
    """**`UX-012`, `T-224`.** Discoverability is the zone's only job.

    The maintainer's report on the built option *E* was that the glyph alone is *"not a very
    pronounced button, people might even miss that they are there"* — and a door nobody finds is a
    door that is not there, since the `⋮` has no accessibility node by design and exists purely to
    be *seen*.

    Asserted as ink inside the zone beyond the glyph itself: a bordered button paints its frame
    across the zone's edges, where bare punctuation leaves them empty. The columns sampled are the
    zone's own left and right edges, which the glyph never reaches.
    """
    delegate = RowDelegate()
    model = _row_with_a_control()
    option = _selectable_row_option()
    index = model.index(0, 0)
    zone = delegate._menu_zone_of(option, index)

    image = paint_rows(model, delegate, 0)

    # The face's own outline, sampled against the pixel just above it — which is inside the zone
    # and outside the button. A border makes those differ; bare punctuation leaves the whole
    # zone the same colour, and the first draft of this test passed on the combo frame's ink
    # until a mutation removing the border failed to fail it.
    face_top = zone.top() + MENU_ZONE_INSET
    above = zone.top() + 1
    x = zone.center().x()
    assert image.pixel(x, face_top) != image.pixel(x, above), (
        "the zone paints one flat colour, so it is still punctuation rather than a button: "
        f"outline {QColor(image.pixel(x, face_top)).name()} against "
        f"{QColor(image.pixel(x, above)).name()} above it"
    )


def test_the_zone_repaints_under_the_pointer(qapp: QApplication) -> None:
    """**The criterion that a style flag cannot satisfy** (`T-224`).

    *"A delegate repaints on mouse move only if the view asks it to, so the regression drives a
    real hover and asserts the painted difference rather than trusting a style flag."* So this
    sends a real `MouseMove` through `editorEvent` and compares the zone's pixels before and
    after — if the hover is recorded but never reaches the paint, the two images are identical and
    this fails.

    **`option.state`'s `State_MouseOver` cannot be used for this**, which is why the delegate
    tracks the zone itself: Qt sets that flag for the whole *row*, so a zone painted from it would
    light up whenever the pointer was anywhere on the row — including over the combo it is carved
    out of.
    """
    delegate = RowDelegate()
    model = _row_with_a_control()
    option = _selectable_row_option()
    index = model.index(0, 0)
    zone = delegate._menu_zone_of(option, index)

    at_rest = _zone_pixels(paint_rows(model, delegate, 0), zone)

    move = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(zone.center()),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    delegate.editorEvent(move, model, option, index)
    hovered = _zone_pixels(paint_rows(model, delegate, 0), zone)

    assert hovered != at_rest, (
        "the zone paints identically with the pointer over it, so the hover state is recorded "
        "and never drawn"
    )


def test_a_hover_elsewhere_on_the_row_leaves_the_zone_at_rest(qapp: QApplication) -> None:
    """The other direction, and the one `State_MouseOver` would fail.

    A pointer on the row but outside the zone must leave the zone unlit — otherwise every row the
    pointer crosses lights its own button, which is worse than no feedback because it stops
    meaning anything.
    """
    delegate = RowDelegate()
    model = _row_with_a_control()
    option = _selectable_row_option()
    index = model.index(0, 0)
    zone = delegate._menu_zone_of(option, index)

    at_rest = _zone_pixels(paint_rows(model, delegate, 0), zone)

    elsewhere = QPointF(float(zone.left() - 40), float(zone.center().y()))
    delegate.editorEvent(
        QMouseEvent(
            QEvent.Type.MouseMove,
            elsewhere,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        ),
        model,
        option,
        index,
    )

    assert _zone_pixels(paint_rows(model, delegate, 0), zone) == at_rest, (
        "the zone lit up for a pointer that was never over it"
    )
