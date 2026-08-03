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

import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Final

import pytest
from PySide6.QtCore import QAbstractListModel, QModelIndex, QRect, Qt
from PySide6.QtGui import QColor, QFontMetrics, QImage, QPainter
from PySide6.QtWidgets import QApplication, QStyleOptionViewItem

from tracks_and_trails.core.paths import thumbnail_cache_directory, thumbnail_cache_path
from tracks_and_trails.ui.row_delegate import (
    DETAIL_ROLE,
    HEADLINE_ROLE,
    HUE_ROLE,
    PADDING,
    PROGRESS_ROLE,
    ROW_HEIGHT,
    STATE_ROLE,
    THUMBNAIL_URL_ROLE,
    RowDelegate,
)
from tracks_and_trails.ui.thumbnails import THUMBNAIL_SIZE, ThumbnailStore

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

#: A real image already in this repository, used as thumbnail bytes. Reusing the application icon
#: rather than committing a second PNG: the claim is that Qt decoded *something* into a pixmap.
IMAGE_SOURCE: Final = REPO_ROOT / "src" / "tracks_and_trails" / "resources" / "icons" / "icon.png"

#: The width a row is rendered at here. Wide enough that nothing under test is elided.
RENDER_WIDTH: Final = 700

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

    # Qt's override names, hence the camelCase.
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
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
    qapp.processEvents()


def spin_until(qapp: QApplication, predicate: Callable[[], bool], timeout: float = 30) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        qapp.processEvents()
        time.sleep(0.005)
    return predicate()


def paint_rows(
    model: RowsModel, delegate: RowDelegate, *indices: int, width: int = RENDER_WIDTH
) -> QImage:
    """Paint the named rows exactly as a view paints its visible ones.

    **The only route to a thumbnail**, which is what makes "row 900 was never painted" a statement
    about this call list rather than about a scroll position.
    """
    image = QImage(width, ROW_HEIGHT * max(len(indices), 1), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        for slot, index in enumerate(indices):
            option = QStyleOptionViewItem()
            option.rect = QRect(0, slot * ROW_HEIGHT, width, ROW_HEIGHT)
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
    # Three lines of text, in the view's own font, must fit as well — the same defect approached
    # from the other side, which is what a large accessibility font would produce.
    assert height >= 3 * QFontMetrics(option.font).height()


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
        paint_rows(model, delegate, index)
        assert spin_until(
            qapp, lambda index=index: f"https://pics.invalid/{index}.jpg" in store.cached_urls
        ), f"row {index}'s picture never arrived"

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
        paint_rows(model, delegate, index)
        assert spin_until(
            qapp, lambda index=index: f"https://pics.invalid/{index}.jpg" in store.cached_urls
        )

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
    assert spin_until(qapp, lambda: thumbnail_cache_path(url, root).exists())

    written = thumbnail_cache_path(url, root)
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

    removed = store.sweep({kept})

    assert removed == 1
    assert thumbnail_cache_path(kept, root).exists(), "a picture a live job still names was deleted"
    assert not thumbnail_cache_path(gone, root).exists(), "a picture nothing names survived"


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
    the queue, which is the property that made 150 rows cost 0.722 s. Comparing two measurements
    taken moments apart on one machine also removes the runner-speed term that made that gate flap
    — a slow runner slows both sides.
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
