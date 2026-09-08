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
    QPoint,
    QPointF,
    QRect,
    QRunnable,
    Qt,
)
from PySide6.QtCore import QPersistentModelIndex as _PersistentIndex
from PySide6.QtGui import QColor, QFontMetrics, QImage, QMouseEvent, QPainter, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QStyle,
    QStyleOptionComboBox,
    QStyleOptionViewItem,
    QWidget,
)

from tracks_and_trails.core.models import MediaKind
from tracks_and_trails.core.paths import thumbnail_cache_directory, thumbnail_cache_path
from tracks_and_trails.core.presets import BUILT_IN_PRESETS
from tracks_and_trails.ui import row_delegate, theme
from tracks_and_trails.ui.row_delegate import (
    ACTION_ROLE,
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
    MEDIA_KIND_ROLE,
    MENU_ZONE_INSET,
    MERGED_BLOCKS,
    MIN_BLOCK_WIDTH,
    MIN_CONTROL_WIDTH,
    MIN_FRACTION_BAR,
    PADDING,
    PRESET_CHOICES_ROLE,
    PRESET_INHERITABLE_ROLE,
    PRESET_INHERITED_ROLE,
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
    VERB_GAP,
    VERBS_ROLE,
    RowDelegate,
    SegmentState,
    _merge,
    _text_lines,
    inherited_entry_text,
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

#: The width a row is rendered at here. Wide enough that no row *text* under test is elided.
#:
#: **The `Download as` control is the exception, and it is deliberate** (`T-284`, `T284-R4`). The
#: control's width does not scale with this: it is a fixed slot, and the label field left inside it
#: after the frame, the arrow and the `⋮` zone is ~146 px whatever `RENDER_WIDTH` is. Two built-in
#: preset names are wider than that, so `test_a_name_too_wide_for_the_field_is_elided_rather_than_
#: clipped` has elision as its subject at this very width.
RENDER_WIDTH: Final = 700

#: Every built-in preset's name, which is what the control has to fit (`T-284`).
DEFAULT_PRESET_NAMES: Final = tuple(preset.name for preset in BUILT_IN_PRESETS)

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
    # gate can see (`docs/project/TESTING.md` §12).
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


def _first_label_pixel(delegate: RowDelegate, slot_left: int) -> int | None:
    """The x of the first pixel the control's *label* inks, found by difference.

    Two rows identical but for the label's text, one of which is a space and inks nothing. The
    frame and the arrow are drawn identically in both, so the leftmost differing column is where
    the text begins — which no amount of style arithmetic can disagree with, because it is what
    was painted.
    """

    def painted(text: str) -> QImage:
        model = RowsModel(
            [
                {
                    HEADLINE_ROLE: "",
                    DETAIL_ROLE: "",
                    STATE_ROLE: "",
                    HUE_ROLE: 0,
                    PRESET_CHOICES_ROLE: ("Best video", "Audio only"),
                    PRESET_ROLE: text,
                }
            ]
        )
        image = QImage(RENDER_WIDTH, ROW_HEIGHT, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        try:
            option = QStyleOptionViewItem()
            option.rect = QRect(0, 0, RENDER_WIDTH, ROW_HEIGHT)
            option.fontMetrics = QFontMetrics(option.font)
            delegate.paint(painter, option, model.index(0, 0))
        finally:
            painter.end()
        return image

    inked, blank = painted("XXXXXX"), painted(" ")
    for x in range(slot_left, RENDER_WIDTH):
        if any(inked.pixel(x, y) != blank.pixel(x, y) for y in range(ROW_HEIGHT)):
            return x
    return None


def test_the_painted_control_insets_its_text_where_the_editor_does(qapp: QApplication) -> None:
    """`T-283`: the label jumped 5 px at the moment of the click.

    **Both routes are measured and neither number is written down here.** A test asserting `7`
    passes today and lies the first time the sheet's padding changes, which is the drift
    `COMBO_PADDING_X` exists to prevent.

    **The painted side is measured from pixels, through `paint`.** A first version asserted
    `_label_box`'s arithmetic directly and a mutation that stopped `_paint_control` calling it
    **survived** — the same shape as `T-244`, where the model offered verbs the delegate never drew
    and each half was tested alone.

    **The sheet is applied to the editor and not to the application**, because that is where the
    defect lives: `QStyleSheetStyle` resolves rules against the widget it is handed, so a
    `QComboBox` rule never reaches a control painted through a `QListView`.

    **This fails if `COMBO_PADDING_X` changes, and that is the honest behaviour rather than a
    limitation to work around.** The painted route *recomputes* the inset as frame plus padding;
    the editor's is whatever the sheet and the style settle on together, and the two agree at `6`
    without being obliged to at every value — measured at `12`, the painted side moves to 13 and
    the editor stays at 7. So this test is a tripwire on the constant, not a proof that any value
    works: changing the padding means re-measuring both routes here, deliberately.
    """
    editor = QComboBox()
    editor.addItem(inherited_entry_text("Best video up to 1080p (MP4)"))
    editor.setStyleSheet(theme.stylesheet(theme.DARK))
    editor.setGeometry(QRect(0, 0, EDITOR_WIDTH, ROW_HEIGHT))
    editor.show()
    qapp.processEvents()
    option = QStyleOptionComboBox()
    editor.initStyleOption(option)
    editor_inset = (
        editor.style()
        .subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxEditField,
            editor,
        )
        .x()
        - option.rect.x()
    )
    editor.deleteLater()
    qapp.processEvents()

    slot_left = RENDER_WIDTH - PADDING - EDITOR_WIDTH
    first = _first_label_pixel(RowDelegate(), slot_left)

    assert first is not None, "the control drew no label at all, so there is nothing to measure"
    painted_inset = first - slot_left
    assert painted_inset == editor_inset, (
        f"the row paints its label {painted_inset} px into the control and the editor it becomes "
        f"on click puts its own {editor_inset} px in, so the text moves under the pointer"
    )
    assert painted_inset >= theme.COMBO_PADDING_X, (
        "the label sits closer to the control's border than the theme's own padding, which is "
        "the report this task was filed from"
    )


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


def test_an_unoverridden_row_draws_the_preset_it_would_follow(qapp: QApplication) -> None:
    """`UX-004`, `T-284`: the control names the preset, not the relation.

    **Two comparisons, because either alone passes on the wrong thing.** A row following
    *Audio only* must draw what a row *overridden to* `Audio only` draws — that is the claim, and a
    fixed word like *"Same as all"* fails it. And it must draw something different from a row
    following *Best video*, which is what fails if the label is any constant at all, including a
    blank.
    """
    delegate = RowDelegate()
    blank: dict[int, Any] = {HEADLINE_ROLE: "", DETAIL_ROLE: "", STATE_ROLE: "", HUE_ROLE: 0}
    choices = ("Best video", "Audio only")

    def row(roles: dict[int, Any]) -> RowsModel:
        return RowsModel([{**blank, PRESET_CHOICES_ROLE: choices, **roles}])

    following_audio = row({PRESET_INHERITABLE_ROLE: True, PRESET_INHERITED_ROLE: "Audio only"})
    overridden_to_audio = row({PRESET_ROLE: "Audio only"})
    following_video = row({PRESET_INHERITABLE_ROLE: True, PRESET_INHERITED_ROLE: "Best video"})

    slot = QRect(
        RENDER_WIDTH - PADDING - EDITOR_WIDTH, PADDING, EDITOR_WIDTH, ROW_HEIGHT - 2 * PADDING
    )
    inherited_pixels = paint_rows(following_audio, delegate, 0).copy(slot)
    assert inherited_pixels == paint_rows(overridden_to_audio, delegate, 0).copy(slot), (
        "a row following Audio only drew something other than the preset's name, so the control "
        "is still saying the relation rather than the value"
    )
    assert inherited_pixels != paint_rows(following_video, delegate, 0).copy(slot), (
        "two rows following different presets drew the same control, so the label is a constant"
    )


def test_the_inherited_entry_carries_the_value_and_the_relation(qapp: QApplication) -> None:
    """`T-284`, ruled 2026-08-30. The entry the user opens onto must not rename what they clicked.

    The closed control shows *Audio only*; the `None` entry must therefore show *Audio only* too,
    with the relation appended — and must not be mistakable for the plain `Audio only` entry one
    line below it, which pins that preset to this row instead of leaving it following.
    """
    delegate = RowDelegate()
    model = RowsModel(
        [
            {
                HEADLINE_ROLE: "",
                DETAIL_ROLE: "",
                STATE_ROLE: "",
                HUE_ROLE: 0,
                PRESET_CHOICES_ROLE: ("Best video", "Audio only"),
                PRESET_INHERITABLE_ROLE: True,
                PRESET_INHERITED_ROLE: "Audio only",
            }
        ]
    )
    index = model.index(0, 0)

    # **The parent is held in a local deliberately.** `createEditor(QWidget(), …)` parents the
    # combo to a temporary, which Qt destroys at the end of that expression and takes the editor
    # with it — the read below then raises *"Internal C++ object already deleted"*. Which is
    # `T-238`'s subject in miniature, met while writing a `T-284` test.
    parent = QWidget()
    editor = delegate.createEditor(parent, _selectable_row_option(), index)
    assert isinstance(editor, QComboBox)
    entries = [(editor.itemText(row), editor.itemData(row)) for row in range(editor.count())]

    assert entries[0] == ("Audio only — following the batch", None), (
        f"the inherited entry does not carry the value and the relation: {entries}"
    )
    assert ("Audio only", "Audio only") in entries, "the preset itself is no longer offered"
    assert entries[0][0] not in [text for text, data in entries[1:]], (
        "the inherited entry reads exactly like a preset entry, so two entries in this list look "
        "identical and mean opposite things"
    )


def test_a_name_too_wide_for_the_field_is_elided_rather_than_clipped(qapp: QApplication) -> None:
    """`T284-R2`, ruled 2026-08-30: the ruled shape truncates, and it must do so legibly.

    **The first version of this measured the wrong rectangle and so proved nothing.** It called
    `_control_of` minus `_menu_zone_of` — 190 px minus 16 — *"available"*, and compared names
    against 174 px. Qt paints into `SC_ComboBoxEditField` after the frame, the arrow and `T-283`'s
    inset: **146 px** here. The longest built-in name is 174 px, so the regression passed at exactly
    the width where the shipped label could not fit.

    Two assertions, and the pixel one is the load-bearing half: a row whose name overflows must
    paint what a row named with the *pre-elided* string paints, which is only true if the delegate
    elided. Asserting the string alone would pass with the elision computed and thrown away.
    """
    delegate = RowDelegate()
    model = _row_with_a_control()
    option = _selectable_row_option()
    index = model.index(0, 0)
    style = QApplication.style()
    box = QStyleOptionComboBox()
    box.rect = delegate._control_of(option, index).adjusted(
        0, 0, -delegate._menu_zone_of(option, index).width(), 0
    )
    field = delegate._label_field(box, style, None).width()

    assert field < box.rect.width(), (
        f"the label field ({field}) is not narrower than the combo it sits in "
        f"({box.rect.width()}), so this is measuring the outer rectangle again"
    )

    metrics = QFontMetrics(option.font)
    overflowing = [name for name in DEFAULT_PRESET_NAMES if metrics.horizontalAdvance(name) > field]
    assert overflowing, (
        f"no built-in preset name exceeds {field} px any more, so this test no longer exercises "
        "elision — if the control grew or the names shrank, re-take the 2026-08-30 ruling"
    )

    widest = max(overflowing, key=metrics.horizontalAdvance)
    elided = metrics.elidedText(widest, Qt.TextElideMode.ElideRight, field)
    assert elided != widest and elided.endswith("…"), f"nothing was elided from {widest!r}"

    blank: dict[int, Any] = {HEADLINE_ROLE: "", DETAIL_ROLE: "", STATE_ROLE: "", HUE_ROLE: 0}

    def painted(name: str) -> QImage:
        rows = RowsModel([{**blank, PRESET_CHOICES_ROLE: (name,), PRESET_ROLE: name}])
        slot = QRect(
            RENDER_WIDTH - PADDING - EDITOR_WIDTH, PADDING, EDITOR_WIDTH, ROW_HEIGHT - 2 * PADDING
        )
        return paint_rows(rows, delegate, 0).copy(slot)

    assert painted(widest) == painted(elided), (
        f"{widest!r} was not painted as {elided!r}, so the label is clipped mid-glyph rather than "
        "elided — which is what the maintainer ruled against on 2026-08-30"
    )
    shortest = min(DEFAULT_PRESET_NAMES, key=metrics.horizontalAdvance)
    assert metrics.horizontalAdvance(shortest) <= field
    assert painted(shortest) != painted(f"{shortest[:-2]}…"), (
        "a name that fits was painted the same as an elided one, so this comparison cannot tell "
        "elision from anything else"
    )


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


# --- the failed row's extra line (T201-R3, ruled 2026-08-14) ----------------------------------

#: What a failed row is given to say, in the words `ui/error_text.py` writes for `FFMPEG_MISSING`.
#: Transcribed rather than imported: these tests are about the *drawing*, and asking production for
#: the string would make them pass on whatever it happens to say.
ACTION_TEXT: Final = "Install ffmpeg, or point Settings at it, then retry."


def a_failed_row(extra: dict[int, Any] | None = None) -> dict[int, Any]:
    """A failed queue row carrying all four of the things the ruling has to keep together.

    The format line, the bar, the verbs and the new action line — the point of the ruling is that
    the action is added *without* displacing any of them, so a row that omitted one would not be
    able to show that.
    """
    row: dict[int, Any] = {
        HEADLINE_ROLE: "Ridgeline in 4K",
        DETAIL_ROLE: "This download needed ffmpeg, which was not found · ERROR: ffmpeg not found",
        HUE_ROLE: 0,
        JOB_ID_ROLE: "job-1",
        PROGRESS_ROLE: 0.62,
        SELECTOR_ROLE: FORMAT_LINE,
        VERBS_ROLE: [Verb.RETRY, Verb.REMOVE],
        ACTION_ROLE: ACTION_TEXT,
    }
    row.update(extra or {})
    return row


def band(row: dict[int, Any], index: int, *, width: int = RENDER_WIDTH) -> QImage:
    """The `index`-th text line of a row, cropped to the strip the row's own text lays out in.

    **Painted at the height `sizeHint` gives that row**, which is what a view does. Painting both
    rows of a comparison at one height instead would be a fairer-looking test and a worse one: the
    format line and the bar would agree while the row a user sees clipped them.

    **The tile and the verbs are cropped out**, and for opposite reasons. The tile does not move
    with the lines — it spans the whole row at a fixed position, so two bands at different line
    numbers hold different slices of one picture and could never compare equal. The verbs do move,
    but `_verb_rects` clamps their height against the bottom of the body, so a button on the last
    line of a five-line row is a pixel shorter than one on the last line of a four-line row and the
    comparison would fail for a reason that is not about position. They are asserted directly, by
    rectangle, in `test_the_verbs_are_hit_tested_on_the_line_they_are_drawn_on`.

    What is left is every line of text and the progress bar, which is what these claims are about.
    """
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, width, 0)
    option.fontMetrics = QFontMetrics(option.font)
    line = option.fontMetrics.height()
    model = RowsModel([row])
    delegate = RowDelegate()
    height = delegate.sizeHint(option, model.index(0, 0)).height()

    option.rect = QRect(0, 0, width, height)
    body, area = delegate._verb_area(option, model.index(0, 0))
    placed = delegate._verb_rects(option.fontMetrics, area, body, model.index(0, 0))
    # The same `verbs_left` `_paint_verbs` returns, so the crop ends exactly where the bar does.
    right = min(rect.left() for _verb, rect in placed) - VERB_GAP if placed else width

    image = paint_rows(model, delegate, 0, width=width, height=height)
    text_left = PADDING + THUMBNAIL_SIZE[0] + GAP
    return image.copy(QRect(text_left, PADDING + index * line, right - text_left, line))


def test_a_failed_row_spends_one_line_on_what_to_do_and_no_other_row_does(
    qapp: QApplication,
) -> None:
    """`T201-R3`, ruled 2026-08-14: option C, and the *only* rows that pay for it.

    **Exactly one line, measured against the row's own font** rather than against a pixel count, so
    a user running a large accessibility font gets the line rather than a clipped one — which is
    `T118-R7` and `T-140`'s clipped child arriving here.

    **And an empty `ACTION_ROLE` costs nothing**, which is the half that keeps `UX-005` §3's
    anatomy: eleven rows in twelve, and every failure with nothing honest to suggest, are drawn at
    the height they were drawn at before this existed.
    """
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, RENDER_WIDTH, 0)
    option.fontMetrics = QFontMetrics(option.font)
    line = option.fontMetrics.height()

    acting = RowsModel([a_failed_row()])
    silent = RowsModel([a_failed_row({ACTION_ROLE: ""})])
    absent = RowsModel([a_download()])
    delegate = RowDelegate()

    tall = delegate.sizeHint(option, acting.index(0, 0)).height()
    quiet = delegate.sizeHint(option, silent.index(0, 0)).height()
    plain = delegate.sizeHint(option, absent.index(0, 0)).height()

    assert tall == (TEXT_LINES + 1) * line + 2 * PADDING, (
        f"a row with an action is {tall}px, not the {TEXT_LINES + 1} lines it draws — so the text "
        "is laid out into space the row does not have and is clipped"
    )
    assert quiet == plain, (
        f"a failure with nothing to suggest is {quiet}px against an ordinary row's {plain}px, so "
        "the height is spent on a line that says nothing"
    )
    assert tall > quiet, "the action line was measured for but the row did not grow"


def test_the_action_line_pushes_the_rest_of_the_row_down_rather_than_over_it(
    qapp: QApplication,
) -> None:
    """The ruling's condition: paint and size derive from one role, and nothing is displaced.

    `T-140` is the record of what a `sizeHint` and a painter disagreeing about a line costs — the
    text was drawn into space the row did not have and the maintainer saw half a line under every
    entry. A new line inserted *above* the format line and the verbs is the same hazard with more
    surfaces to get wrong, so the assertion is not "the action appears" but **the whole tail of the
    row is drawn identically, one line lower**.

    The last band is the progress bar's; the verbs share that line and are cropped out of it for
    the reason `band` gives, then asserted by rectangle in the test below.
    """
    acting = a_failed_row()
    silent = a_failed_row({ACTION_ROLE: ""})

    assert band(acting, 2) != band(silent, 2), (
        "the third line is drawn the same with and without an action, so the action is not there"
    )
    assert band(acting, 3) == band(silent, 2), (
        "the format line is not drawn identically one line lower, so the action displaced it "
        "instead of pushing it down — UX-005 §6's text is the half that cannot give"
    )
    assert band(acting, 4) == band(silent, 3), (
        "the progress bar is not drawn identically one line lower, so it is left under the "
        "action's own text or under the format line"
    )


def test_the_verbs_are_hit_tested_on_the_line_they_are_drawn_on(qapp: QApplication) -> None:
    """The same claim from the hit-test side, which is where `_verb_rects` could still disagree.

    `_paint_text` and `_verb_rects` are separate readers of `_action_lines`, and the paint
    comparison above cannot see a layout that draws in the right place while resolving clicks a
    line above it — `T118-R12` and `T-160` are this project's record of exactly that split.
    """
    delegate = RowDelegate()
    option = QStyleOptionViewItem()
    line = QFontMetrics(option.font).height()
    option.rect = QRect(0, 0, RENDER_WIDTH, (TEXT_LINES + 1) * line + 2 * PADDING)
    option.fontMetrics = QFontMetrics(option.font)

    acting = RowsModel([a_failed_row()])
    silent = RowsModel([a_failed_row({ACTION_ROLE: ""})])

    tops = []
    for model in (acting, silent):
        body, area = delegate._verb_area(option, model.index(0, 0))
        placed = delegate._verb_rects(option.fontMetrics, area, body, model.index(0, 0))
        assert placed, "no verb was laid out at all, so nothing here is being measured"
        tops.append(placed[0][1].top())
        assert placed[0][1].bottom() <= body.bottom(), (
            "a verb is laid out past the bottom of the row's body, so it is drawn clipped"
        )

    assert tops[0] == tops[1] + line, (
        f"the verbs on a row with an action are hit-tested at y={tops[0]} and on one without at "
        f"y={tops[1]}, which is not one line apart — the buttons and the action share a line"
    )


# --- an expanded playlist entry keeps its own verbs (T-244) -----------------------------------


def a_playlist_child(extra: dict[int, Any] | None = None) -> dict[int, Any]:
    """One entry of an opened playlist, with the verbs its state permits.

    `DEPTH_ROLE` is what makes it a child, and it is the whole of the defect: the row is *sized*
    from the child anatomy and its verbs were *placed* from the parent's.
    """
    row: dict[int, Any] = {
        HEADLINE_ROLE: "01 Prelude of Light",
        DETAIL_ROLE: "Trail Sounds · 4:12 · The connection to the site failed",
        HUE_ROLE: 0,
        DEPTH_ROLE: 1,
        JOB_ID_ROLE: "entry-1",
        VERBS_ROLE: [Verb.RETRY, Verb.REMOVE],
    }
    row.update(extra or {})
    return row


#: The four shapes a child row comes in, which is every combination of its two optional lines.
CHILD_SHAPES: Final = [
    ("two lines", {}),
    ("a format of its own", {SELECTOR_ROLE: FORMAT_LINE}),
    ("an action line", {ACTION_ROLE: ACTION_TEXT}),
    ("both", {SELECTOR_ROLE: FORMAT_LINE, ACTION_ROLE: ACTION_TEXT}),
]


@pytest.mark.parametrize(("shape", "extra"), CHILD_SHAPES, ids=[s for s, _ in CHILD_SHAPES])
def test_an_expanded_playlist_child_draws_the_verbs_it_offers(
    qapp: QApplication, shape: str, extra: dict[int, Any]
) -> None:
    """**`T-244`.** An entry offered `Retry` and `Remove` and drew neither — at every width.

    Not a clipped control, which a user can at least see: **no control**. `_verb_rects` measured
    every row's last line from the top-level `TEXT_LINES` while `sizeHint` shortened a child to
    `CHILD_TEXT_LINES`, so the baseline landed below the child's own body, the height clamped to
    zero and the layout returned an empty list. The playlist header's own verbs were fine
    throughout, which is why nothing looked broken from the outside.

    **Swept, for `SWEEP_WIDTHS`' own reason**: a collision that appears over a range and vanishes
    again is not caught by rendering one width. **And all four child shapes**, because the child
    anatomy has two optional lines and the last line is a different one in each.
    """
    row = a_playlist_child(extra)
    offered = set(row[VERBS_ROLE])
    delegate = RowDelegate()

    for width in SWEEP_WIDTHS:
        model = RowsModel([row])
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, width, 0)
        option.fontMetrics = QFontMetrics(option.font)
        option.rect = QRect(0, 0, width, delegate.sizeHint(option, model.index(0, 0)).height())

        body, area = delegate._verb_area(option, model.index(0, 0))
        placed = delegate._verb_rects(option.fontMetrics, area, body, model.index(0, 0))
        drawn = {verb for verb, _ in placed if verb is not None}
        overflowed = bool(placed) and any(verb is None for verb, _ in placed)

        assert drawn or overflowed, (
            f"at {width}px a child with {shape} offers {sorted(v.value for v in offered)} and "
            "draws nothing at all — not even the overflow that would make them reachable"
        )
        assert drawn <= offered, (
            f"at {width}px the row drew {sorted(v.value for v in drawn - offered)}, which the "
            "model never offered"
        )
        for verb, rect in placed:
            assert body.top() <= rect.top() and rect.bottom() <= body.bottom(), (
                f"at {width}px the {verb} button on a child with {shape} is laid out at "
                f"{rect.top()}..{rect.bottom()} against a body of {body.top()}..{body.bottom()}, "
                "so it is drawn clipped or outside the row"
            )


@pytest.mark.parametrize(("shape", "extra"), CHILD_SHAPES, ids=[s for s, _ in CHILD_SHAPES])
def test_a_child_row_is_not_made_taller_by_carrying_verbs(
    qapp: QApplication, shape: str, extra: dict[int, Any]
) -> None:
    """The fix spends no height, which is `UX-005` row 9c's economy and the reason for it.

    An entry that grew a line for its buttons would undo the trade row 9c made — a sixteen-item
    playlist is exactly where there is least room to waste. The verbs share the row's last line
    instead, and the text on that line yields its right-hand end to them.
    """
    delegate = RowDelegate()
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, RENDER_WIDTH, 0)
    option.fontMetrics = QFontMetrics(option.font)

    with_verbs = RowsModel([a_playlist_child(extra)])
    without = RowsModel([a_playlist_child({**extra, VERBS_ROLE: []})])

    tall = delegate.sizeHint(option, with_verbs.index(0, 0)).height()
    short = delegate.sizeHint(option, without.index(0, 0)).height()

    assert tall == short, (
        f"a child with {shape} is {tall}px when it carries verbs and {short}px when it does not, "
        "so the buttons are being paid for in height row 9c bought"
    )


def child_strip(row: dict[int, Any], *, width: int = RENDER_WIDTH) -> QImage:
    """The part of a child's last line the buttons occupy, cropped from the painted row.

    Only the buttons are drawn there, so two rows whose *text* differs must produce an identical
    strip — and if the text runs on under them, they will not.
    """
    delegate = RowDelegate()
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, width, 0)
    option.fontMetrics = QFontMetrics(option.font)
    line = option.fontMetrics.height()
    model = RowsModel([row])
    height = delegate.sizeHint(option, model.index(0, 0)).height()
    option.rect = QRect(0, 0, width, height)

    body, area = delegate._verb_area(option, model.index(0, 0))
    placed = delegate._verb_rects(option.fontMetrics, area, body, model.index(0, 0))
    assert placed, "no verb was laid out, so there is no strip to compare"
    left = min(rect.left() for _verb, rect in placed) - VERB_GAP
    top = PADDING + (_text_lines(model.index(0, 0)) - 1) * line

    image = paint_rows(model, delegate, 0, width=width, height=height)
    return image.copy(QRect(left, top, width - left, line))


#: For each child shape, the role whose text lands on that shape's **last** line.
#:
#: The mapping is the point of the parametrisation rather than a convenience: which line is last
#: differs per shape, and a test that only ever varied the detail would leave the format and action
#: paths free to draw underneath the buttons. One did, and survived a mutation until this said so.
LAST_LINE_ROLE: Final = [
    ("two lines", {}, DETAIL_ROLE),
    ("a format of its own", {ACTION_ROLE: ""}, SELECTOR_ROLE),
    ("an action line", {SELECTOR_ROLE: ""}, ACTION_ROLE),
    ("both", {ACTION_ROLE: ACTION_TEXT}, SELECTOR_ROLE),
]


@pytest.mark.parametrize(
    ("shape", "extra", "role"), LAST_LINE_ROLE, ids=[s for s, _, _ in LAST_LINE_ROLE]
)
def test_a_child_row_does_not_draw_its_last_line_under_the_buttons(
    qapp: QApplication, shape: str, extra: dict[int, Any], role: int
) -> None:
    """Row 9c leaves an entry two lines, so one of them is also the buttons' line.

    A top-level row has a spare line for its verbs; a child does not, and giving it one would spend
    the height row 9c bought. So the text yields its right-hand end instead — and this is the half
    a layout can get right while still drawing a sentence underneath three buttons.

    **Asserted as: the buttons' own strip is identical whatever the text says.** Nothing but the
    verbs is drawn there, so a long string and a short one must be pixel-identical across it. It
    cannot pass by both being blank, because the buttons are in the strip; and the two rows keep
    the same line count, so they are the same height and the strip is the same band.

    **Per shape, because the last line is a different one in each** — the detail, the format line,
    or the action.
    """
    long_text = "a long line that runs the whole width and then some more " * 3
    loud = a_playlist_child({**extra, role: long_text})
    quiet = a_playlist_child({**extra, role: "x"})

    assert child_strip(loud) == child_strip(quiet), (
        f"on a child with {shape} the last line is drawn underneath its own buttons — the text "
        "did not give up the width the verbs occupy, so the two overlap"
    )


def test_a_child_verb_is_triggered_where_it_is_drawn(qapp: QApplication) -> None:
    """Paint and click resolve through one rectangle — asserted, not inherited (`T-244`).

    `editorEvent` and `_paint_verbs` both call `_verb_rects`, so they agree by construction — and
    *"by construction"* is what `T118-R12` and `T-160` were both told before a control turned out
    to be drawn where nobody clicked. This drives a real click at the centre of the rectangle the
    layout reports and asserts the signal names that verb.

    **Release, not press**: a verb fires on the way up, and the press is consumed only by the `⋮`
    zone (`T224-R1`). Driving the press alone found nothing here, which is the test being wrong
    about the control rather than the control being wrong.
    """
    delegate = RowDelegate()
    model = RowsModel([a_playlist_child()])
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, RENDER_WIDTH, 0)
    option.fontMetrics = QFontMetrics(option.font)
    option.rect = QRect(0, 0, RENDER_WIDTH, delegate.sizeHint(option, model.index(0, 0)).height())

    body, area = delegate._verb_area(option, model.index(0, 0))
    placed = delegate._verb_rects(option.fontMetrics, area, body, model.index(0, 0))
    assert placed, "no verb was laid out, so this proves nothing about clicking one"

    fired: list[tuple[str, Any]] = []
    delegate.verb_triggered.connect(lambda job_id, verb: fired.append((job_id, verb)))
    for verb, rect in placed:
        fired.clear()
        _press(delegate, model, option, rect.center())
        _release(delegate, model, option, rect.center())
        assert fired == [("entry-1", verb)], (
            f"clicking the centre of the {verb} button on a playlist entry produced {fired}; the "
            "rectangle it is drawn in is not the rectangle the click resolves"
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
    appears — `docs/project/TESTING.md` §13's rule about a test that transcribes rather than
    re-derives does not apply, because the property *is* "no two of them agree" rather than a
    specification the test should hold independently.
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


# --- T-217: a placeholder tile says what it is standing in for --------------------------------


def _tile_ink(image: QImage, *, inset: int = 0) -> set[int]:
    """Every distinct colour in the first row's thumbnail slot.

    `inset` skips that many pixels of border. The tile draws its own outline a shade lighter than
    its fill, which is enough on its own to satisfy *"something here is lighter than the block"* —
    so the test that asks whether the glyph is visible insets past it. That is not hypothetical:
    the first draft of that test passed while the glyph was not being drawn at all.
    """
    width, height = THUMBNAIL_SIZE
    return {
        image.pixel(x, y)
        for y in range(PADDING + inset, min(PADDING + height - inset, image.height()))
        for x in range(PADDING + inset, min(PADDING + width - inset, image.width()))
    }


def _placeholder_image(kind: MediaKind | None, hue: int = 120) -> QImage:
    """One row with no artwork, painted. No `ThumbnailStore`, so the derived tile is what draws."""
    extra: dict[int, Any] = {HUE_ROLE: hue}
    if kind is not None:
        extra[MEDIA_KIND_ROLE] = kind
    model = RowsModel([a_row(0, extra=extra)])
    return paint_rows(model, RowDelegate(), 0)


def test_a_row_without_artwork_is_marked_rather_than_left_a_colour_block(
    qapp: QApplication,
) -> None:
    """**`T-217`.** A flat rectangle reads as a broken image, which is the opposite of the point.

    `_paint_tile`'s existing rule is *"never an empty box"* — a column of empty wells reads as a
    broken application. The derived tile answered that with a colour and stopped there, so it said
    *something is missing here* without saying what. Asserted as strictly more distinct colours in
    the tile than the two the bare block has (its fill and its border).
    """
    bare = _tile_ink(_placeholder_image(None))
    marked = _tile_ink(_placeholder_image(MediaKind.AUDIO))

    assert len(marked) > len(bare), (
        f"the marked tile has no more ink than the plain one ({len(marked)} colours against "
        f"{len(bare)}), so the glyph is not being drawn"
    )


def test_audio_and_video_placeholders_can_be_told_apart(qapp: QApplication) -> None:
    """The criterion's second half, and the one a single glyph would pass without meeting.

    A fix that drew the same mark for both would satisfy *"reads as intentional"* and still leave
    the two kinds indistinguishable — which is the thing worth knowing at a glance while a queue
    is still resolving.
    """
    audio = _tile_ink(_placeholder_image(MediaKind.AUDIO))
    video = _tile_ink(_placeholder_image(MediaKind.VIDEO))

    assert audio != video, "audio and video draw the same placeholder"


def test_the_video_mark_is_a_film_frame_and_not_a_play_triangle(qapp: QApplication) -> None:
    """**`T217-R1`.** The task scopes *a note for audio, a film frame for video*.

    The first build drew `▶`. It satisfied every other assertion here — it is a mark, it differs
    from the note, it reads against the block — and it says *this will play* rather than *this is
    video*, which is a different statement. So the shape needs pinning, not just the presence of
    ink.

    Two properties a filled triangle fails and a frame passes:

    - **It is hollow.** A frame is an outline; its middle is the tile's own colour. A triangle's
      middle is ink.
    - **It is left-right symmetric.** A triangle points somewhere; a frame does not.
    """
    hue = 200
    image = _placeholder_image(MediaKind.VIDEO, hue=hue)
    block = QColor(image.pixel(PADDING + 2, PADDING + 2))

    width, height = THUMBNAIL_SIZE
    left, top = PADDING, PADDING

    def inked(x: int, y: int) -> bool:
        return QColor(image.pixel(x, y)).value() > block.value() + 6

    centre_x, centre_y = left + width // 2, top + height // 2
    assert not inked(centre_x, centre_y), (
        "the middle of the mark is inked, so it is a solid shape rather than a frame"
    )

    # Symmetry is measured about the **mark's own** bounding box, not the tile's centre: the
    # frame is centred with `QRect.moveCenter`, which lands a pixel off centre for an even-width
    # tile, and that is a placement detail rather than the shape being asymmetric.
    rows = range(top + 2, top + height - 2)
    columns = range(left + 2, left + width - 2)
    per_column = [sum(1 for y in rows if inked(x, y)) for x in columns]
    inked_columns = [i for i, count in enumerate(per_column) if count]
    assert inked_columns, "nothing is drawn in the tile at all"

    span = per_column[inked_columns[0] : inked_columns[-1] + 1]
    difference = sum(abs(a - b) for a, b in zip(span, reversed(span), strict=True))
    assert difference == 0, (
        f"the mark is not left-right symmetric (mirror difference {difference}), so it points "
        f"somewhere — a frame does not. Column profile: {span}"
    )


def test_the_glyph_does_not_cover_the_hue_that_tells_rows_apart(qapp: QApplication) -> None:
    """*Over* the block, not instead of it — the hue is a working signal already.

    `placeholder_hue` derives a per-URL colour so a loading queue is not a column of identical
    tiles. A glyph painted opaquely across the tile would trade that for a mark that is the same on
    every row.

    **Asserted as the fill still being the tile's majority colour, not merely as it surviving
    somewhere.** A mutation that drew the mark opaque at three times the size left the fill in the
    corners, so a "is the fill still present" check passed a tile the glyph had effectively taken
    over.
    """
    hue = 200
    plain = _placeholder_image(None, hue=hue)
    fill = plain.pixel(PADDING + 4, PADDING + 4)

    marked = _placeholder_image(MediaKind.VIDEO, hue=hue)
    width, height = THUMBNAIL_SIZE
    pixels = [
        marked.pixel(x, y)
        for y in range(PADDING + 2, min(PADDING + height - 2, marked.height()))
        for x in range(PADDING + 2, min(PADDING + width - 2, marked.width()))
    ]
    share = pixels.count(fill) / len(pixels)
    assert share > 0.5, (
        f"the tile's own hue is only {share:.0%} of its interior, so the glyph has taken the tile "
        "over rather than marking it"
    )


@pytest.mark.parametrize("kind", [MediaKind.AUDIO, MediaKind.VIDEO])
def test_the_glyph_reads_against_the_tile_it_is_drawn_on(
    qapp: QApplication, kind: MediaKind
) -> None:
    """*"An icon that vanishes into the ground is this task's defect to not create."*

    `T-203`'s phrasing, reused by this task's entry on purpose. The check is not that the glyph
    exists but that it is **lighter than the block it sits on** — the tile is drawn at HSV value
    110 and the ink at 235, so this holds in either palette, because the ground here is this
    delegate's own fill rather than the window's. A glyph tinted down until it matched the block
    would pass the *"more colours"* test above and fail this one.
    """
    hue = 200
    image = _placeholder_image(kind, hue=hue)
    block = QColor(image.pixel(PADDING + 4, PADDING + 4))

    lighter = [
        QColor(pixel)
        for pixel in _tile_ink(image, inset=2)
        if QColor(pixel).value() > block.value() + 10 and QColor(pixel).alpha() > 0
    ]
    assert lighter, (
        f"nothing in the tile is lighter than its own block (value {block.value()}), so the glyph "
        "has vanished into the ground"
    )


def test_a_row_whose_kind_is_not_one_thing_keeps_the_plain_block(qapp: QApplication) -> None:
    """**`None` is an answer, not a gap** — the mixed playlist group.

    A part-retargeted playlist holds audio and video at once, which is the same split
    `PRESET_PLACEHOLDER_ROLE` answers *"Mixed"* for. Marking such a group with either glyph would
    assert something false about half its members, so it is left unmarked.

    This also pins the compatibility property the role's comment claims: a model that has never
    heard of `MEDIA_KIND_ROLE` returns `None` for it and gets exactly the tile it drew before.
    """
    assert _tile_ink(_placeholder_image(None)) == _tile_ink(_placeholder_image(None, hue=120))
    unmarked = _tile_ink(_placeholder_image(None))
    assert len(unmarked) <= 3, (
        f"the unmarked tile has {len(unmarked)} colours, so something is being drawn on a row "
        "whose kind is not one thing"
    )


def test_real_artwork_replaces_the_glyph_entirely(
    qapp: QApplication, stores: Callable[..., ThumbnailStore]
) -> None:
    """A picture is not a picture with a music note printed on it.

    The glyph marks *absence*; the moment there is artwork the placeholder path is not taken at
    all, so nothing of the derived tile can survive into the drawn thumbnail. Asserted against the
    **unmarked** placeholder rather than against the marked one, because a fix that drew the glyph
    over real artwork would still differ from the marked placeholder and pass a looser check.
    """
    store = stores(loader=FakeLoader(IMAGE_SOURCE.read_bytes()))
    delegate = RowDelegate(thumbnails=store)
    marked = {HUE_ROLE: 120, MEDIA_KIND_ROLE: MediaKind.AUDIO}
    model = RowsModel([a_row(0, thumbnail="https://pics.invalid/0.jpg", extra=marked)])

    url = "https://pics.invalid/0.jpg"
    paint_rows(model, delegate, 0)
    assert spin_until(qapp, holds(store, url)), "the picture never arrived"

    with_glyph_role = _tile_ink(paint_rows(model, delegate, 0))
    assert with_glyph_role != _tile_ink(_placeholder_image(None, hue=120)), (
        "the artwork is not being drawn at all"
    )

    # **The same artwork with the role absent.** If the placeholder path leaks into the drawn
    # thumbnail, these two differ; if artwork replaces it entirely, they are identical. Comparing
    # against the *placeholder's* glyph colours instead does not work and is not hypothetical — a
    # mutation that drew the mark over real artwork passed that version of this test, because the
    # mark blends with the picture underneath and so lands on different colours than it does over
    # a flat block.
    plain_model = RowsModel([a_row(0, thumbnail=url, extra={HUE_ROLE: 120})])
    without = _tile_ink(paint_rows(plain_model, delegate, 0))
    assert with_glyph_role == without, "the placeholder glyph is still drawn over real artwork"


def _press(
    delegate: RowDelegate, model: RowsModel, option: QStyleOptionViewItem, at: QPoint
) -> None:
    delegate.editorEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(at),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        ),
        model,
        option,
        model.index(0, 0),
    )


def _release(
    delegate: RowDelegate, model: RowsModel, option: QStyleOptionViewItem, at: QPoint
) -> None:
    delegate.editorEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(at),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        ),
        model,
        option,
        model.index(0, 0),
    )


def test_the_zone_is_drawn_sunken_while_the_button_is_held(qapp: QApplication) -> None:
    """**`T224-R1`.** The pressed face was set and cleared inside one synchronous block.

    The first build assigned `_pressed_zone` on *release*, asked for an asynchronous
    `viewport().update()`, and cleared the value on the next line — so no paint could ever observe
    it and the sunken look was unreachable. The three original tests covered only the border and
    the hover, so nothing failed.

    This drives a real `MouseButtonPress` and paints **while the button is still down**, which is
    the only moment the state is supposed to exist.
    """
    delegate = RowDelegate()
    model = _row_with_a_control()
    option = _selectable_row_option()
    index = model.index(0, 0)
    zone = delegate._menu_zone_of(option, index)

    at_rest = _zone_pixels(paint_rows(model, delegate, 0), zone)
    _press(delegate, model, option, zone.center())
    held = _zone_pixels(paint_rows(model, delegate, 0), zone)

    assert held != at_rest, (
        "the zone paints identically with the button held down, so the pressed state is not "
        "reachable by any paint"
    )


def test_the_pressed_face_differs_from_the_hover_face(qapp: QApplication) -> None:
    """Three looks, not two — otherwise the press is a hover with extra steps.

    A press over the zone is also a pointer over the zone, so an implementation that only tracked
    hover would satisfy the test above while having no pressed state at all.
    """
    delegate = RowDelegate()
    model = _row_with_a_control()
    option = _selectable_row_option()
    index = model.index(0, 0)
    zone = delegate._menu_zone_of(option, index)

    delegate.editorEvent(
        QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(zone.center()),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        ),
        model,
        option,
        index,
    )
    hovered = _zone_pixels(paint_rows(model, delegate, 0), zone)

    _press(delegate, model, option, zone.center())
    held = _zone_pixels(paint_rows(model, delegate, 0), zone)

    assert held != hovered, "pressed and hovered paint the same, so the press is not its own state"


def test_the_zone_comes_back_up_before_the_menu_opens(qapp: QApplication) -> None:
    """A button left sunken behind a menu is worse than one that never moved.

    The menu takes the pointer, so the face has to be released *before* the signal is emitted —
    asserted inside the handler, because that is the moment the menu would be appearing.
    """
    delegate = RowDelegate()
    model = _row_with_a_control()
    option = _selectable_row_option()
    index = model.index(0, 0)
    zone = delegate._menu_zone_of(option, index)

    at_rest = _zone_pixels(paint_rows(model, delegate, 0), zone)
    seen: list[int | None] = []
    delegate.menu_requested.connect(lambda _where: seen.append(delegate._pressed_zone))

    _press(delegate, model, option, zone.center())
    _release(delegate, model, option, zone.center())

    assert seen == [None], f"the zone was still {seen} when the menu opened"
    assert _zone_pixels(paint_rows(model, delegate, 0), zone) == at_rest, (
        "the zone is still drawn pressed after the menu opened"
    )


def test_a_press_that_wanders_off_the_zone_does_not_leave_it_stuck_down(
    qapp: QApplication,
) -> None:
    """The other way a button gets stuck: pressed inside, released somewhere else.

    Qt delivers the release to the widget that took the press, so without an unconditional clear
    the face would stay drawn sunken until the next mouse move happened to cross the zone.
    """
    delegate = RowDelegate()
    model = _row_with_a_control()
    option = _selectable_row_option()
    index = model.index(0, 0)
    zone = delegate._menu_zone_of(option, index)

    at_rest = _zone_pixels(paint_rows(model, delegate, 0), zone)
    _press(delegate, model, option, zone.center())
    _release(delegate, model, option, QPoint(zone.left() - 60, zone.center().y()))

    assert delegate._pressed_zone is None
    assert _zone_pixels(paint_rows(model, delegate, 0), zone) == at_rest, (
        "the zone is still drawn pressed after a release that landed elsewhere"
    )


# --- T-297: Qt keeps index widgets in the same map as item editors ----------------------------


def test_the_delegate_leaves_a_widget_that_is_not_its_own_editor_at_the_row_s_size(
    qapp: QApplication,
) -> None:
    """`T-297`: an open row's panel was being sized as if it were the row's format combo.

    `QAbstractItemView` keeps `setIndexWidget` widgets in **the same map as item editors**, so every
    `updateGeometries()` pass hands this delegate the panel. `updateEditorGeometry` applied
    `_control_of` to whatever it was given — the small control slot — and a 354 px panel became
    **26 px**. A resize calls `updateGeometries()` once per step, so the panel collapsed and was
    restored once per step, and the view painted the row inside each gap: `paint` draws the
    thumbnail on every row it is given, because an open one is supposed to be covered. Measured
    under a compositor at `docs/project/evidence/2026-09-01-T297-panel-collapses-during-resize.md`,
    where the walk produced 107 collapses in 110 steps.

    **Both branches, because the guard is the fix.** A widget that is not this delegate's editor
    keeps the row's rectangle; the delegate's own combo box still gets the control slot it is
    painted in (`T118-R12`), and a fix that skipped both would move the control away from the
    affordance the user clicked.
    """
    delegate = RowDelegate()
    model = RowsModel([a_row(0)])
    index = model.index(0, 0)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, RENDER_WIDTH, 354)
    option.fontMetrics = QFontMetrics(option.font)

    panel = QWidget()
    delegate.updateEditorGeometry(panel, option, index)

    assert panel.geometry() == option.rect, (
        f"the panel was sized to {panel.geometry()} instead of the row's {option.rect}. Qt hands "
        "index widgets to updateEditorGeometry, and sizing one like the format control collapses "
        "an open panel to the control slot on every layout pass"
    )

    # **The parent is held in a local deliberately**, as this file already records one test over:
    # `createEditor(QWidget(), …)` parents the editor to a temporary Python frees immediately, and
    # the editor goes with it.
    parent = QWidget()
    editor = delegate.createEditor(parent, option, index)
    delegate.updateEditorGeometry(editor, option, index)

    assert editor.geometry() != option.rect, (
        "the delegate's own combo box was given the whole row instead of the slot `paint` reserves "
        "for it, so the control no longer sits where the affordance was drawn"
    )
    assert editor.geometry().height() < option.rect.height()
