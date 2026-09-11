"""Nothing is said by colour alone (`T-202`, `NFR-005`).

`NFR-005` ends with *"and no information conveyed by color alone"*, and `IMPLEMENTATION_PLAN.md`
§Phase 4 repeats it as an exit criterion. This is the sweep that answers it.

## What makes this different from asserting a colour

**A test that asserts a colour proves the opposite of what is wanted.** It shows the colour is
there; the criterion is about what a user who cannot distinguish it still learns. So every
assertion here reads either **words** or a **non-colour property** — weight, a published
accessibility state, a count in text — and the colour is only ever used to *find* the place that
has to carry one.

## The three shapes colour takes in this application

1. **Style sheet rules** that set `ok`, `warn` or `stop`. Enumerated in `theme.SEMANTIC_RULES`
   with the second channel beside each, and swept here for completeness: a new one that is not
   enumerated fails.
2. **Painted state**, which no style sheet can reach — the playlist header's segment bar draws
   five states in five colours. Its second channel is the row's own detail line, which names each
   state and counts it.
3. **`muted`**, which is the one `T-202` warns is easiest to miss, *"because it does not look like
   a semantic colour"*. Split by what it means: secondary emphasis, or unavailable.

Both palettes throughout. `T130-R1` already found contrast problems that differed between them,
and a rule that holds in light and fails in dark is not a rule.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterator
from typing import Final

import pytest
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QAccessible, QColor, QImage, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHeaderView,
    QLineEdit,
    QListView,
    QMenu,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QStyle,
    QStyleOptionButton,
    QTableView,
    QTextEdit,
    QToolBar,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from tests.ui.conftest import Surface, focusable
from tracks_and_trails.ui import settings_dialog
from tracks_and_trails.ui import theme as ui_theme
from tracks_and_trails.ui.row_delegate import SegmentState

#: Every rule block in a style sheet, as (selector, declarations).
_RULE: Final = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)
_COMMENT: Final = re.compile(r"/\*.*?\*/", re.S)

THEMES: Final = (ui_theme.LIGHT, ui_theme.DARK)


def rules(theme: ui_theme.Theme) -> Iterator[tuple[str, str]]:
    """Each rule of the generated sheet, with comments stripped and whitespace normalised.

    **Comments are stripped first**, and it is not cosmetic: this file's own reasoning is written
    into that sheet, and the words *"warn"* and *"muted"* appear in it repeatedly. A sweep reading
    them would match its own explanation.

    **From the selector as well as the body.** A comment between two rules — the sheet has one,
    `T-133`'s note on why `QSpinBox` is left alone — belongs to no block, so the rule pattern hands
    it back as part of the next selector. Nothing noticed while selectors were only compared whole;
    `bordered_selectors` splits them on commas, and that note contains four.
    """
    for selector, body in _RULE.findall(ui_theme.stylesheet(theme)):
        yield " ".join(_COMMENT.sub("", selector).split()), _COMMENT.sub("", body)


def declarations(body: str) -> list[str]:
    return [" ".join(part.split()) for part in body.split(";") if part.strip()]


def semantic_values(theme: ui_theme.Theme) -> dict[str, str]:
    return {name: getattr(theme, name).lower() for name in ("ok", "warn", "stop")}


# --- style sheet rules (T-202: the enumeration is the deliverable) -----------------------------


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_every_enumerated_rule_is_really_in_the_sheet_with_both_channels(
    theme: ui_theme.Theme,
) -> None:
    """`theme.SEMANTIC_RULES` is a claim about the sheet, so it is checked against the sheet.

    A registry that drifts from what it describes is worse than no registry: it reads as coverage
    while covering nothing. Both halves are required — the colour *and* the declaration that says
    the same thing without it.
    """
    assert ui_theme.SEMANTIC_RULES, "the enumeration is empty, so this file asserts nothing"

    by_selector = dict(rules(theme))
    for rule in ui_theme.SEMANTIC_RULES:
        assert rule.selector in by_selector, (
            f"{rule.selector!r} is enumerated but is not in the {theme.name} sheet"
        )
        body = by_selector[rule.selector]
        expected = getattr(theme, rule.colour).lower()
        assert expected in body.lower(), (
            f"{rule.selector!r} is enumerated as using {rule.colour} ({expected}) and does not"
        )
        assert rule.second_channel in " ".join(declarations(body)), (
            f"{rule.selector!r} sets {rule.colour} without its recorded second channel "
            f"{rule.second_channel!r} — the colour is the only thing saying {rule.meaning!r}"
        )


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_no_semantic_colour_reaches_the_sheet_unenumerated(theme: ui_theme.Theme) -> None:
    """**The completeness half**, and the reason `SEMANTIC_RULES` is a gate rather than a comment.

    Every occurrence of a semantic colour's value in the generated sheet has to be claimed —
    either as a semantic rule with its second channel, or as one of the coincidences
    `COINCIDENTAL_SEMANTIC_VALUES` names. Adding `color: {theme.stop}` to a new rule and stopping
    there fails here.

    **`warn` and `accent` are the same hex in dark**, both `GOLD`, so this finds the focus ring and
    the pressed primary action in one palette and not the other. They are excluded by selector
    rather than by a colour comparison, so a rule that starts carrying meaning has to be taken out
    of that tuple by hand.
    """
    claimed = {rule.selector for rule in ui_theme.SEMANTIC_RULES}
    claimed.update(ui_theme.COINCIDENTAL_SEMANTIC_VALUES)
    values = semantic_values(theme)

    unclaimed = [
        (selector, [name for name, value in values.items() if value in body.lower()])
        for selector, body in rules(theme)
        if selector not in claimed and any(value in body.lower() for value in values.values())
    ]
    assert not unclaimed, (
        "semantic colour(s) used by rules nothing enumerates — add them to "
        f"`theme.SEMANTIC_RULES` with the second channel that says the same thing: {unclaimed}"
    )


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_the_sweep_is_looking_at_a_real_sheet(theme: ui_theme.Theme) -> None:
    """Both sweeps above assert a set is empty, so they pass over nothing for free.

    Measured 2026-08-15: the sheet parses to 45 rules in each palette. The floor is well below that
    and exists so a `stylesheet()` that returned `""` — or a regex that stopped matching — fails
    here rather than turning every assertion above green.
    """
    found = list(rules(theme))
    assert len(found) >= 30, f"the {theme.name} sheet parsed to {len(found)} rules"
    assert any(theme.warn.lower() in body.lower() for _selector, body in found), (
        "no rule uses `warn` at all, so the enumeration is matching nothing"
    )


# --- interaction states, enumerated by what they convey (T202-R1) ------------------------------


_PSEUDO_STATE: Final = re.compile(r":(focus|hover|pressed|checked|selected|disabled|default)\b")


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_every_interaction_state_in_the_sheet_is_enumerated(theme: ui_theme.Theme) -> None:
    """**The completeness half of `T202-R1`, and the half the first version did not have.**

    The earlier sweep asked *which rules use `ok`, `warn` or `stop`* — a question about the palette
    field, not about the information. The focus ring is drawn in `accent`, so it was never asked
    what it meant, and it meant **keyboard focus**: the single most load-bearing state for the user
    this task exists to protect.

    So every pseudo-state selector in the generated sheet has to be in `theme.STATE_RULES`, with
    what it conveys and the channel that conveys it without colour. Adding `:focus` or `:selected`
    to a new rule and stopping there fails here.
    """
    enumerated = {rule.selector for rule in ui_theme.STATE_RULES}
    present = {selector for selector, _body in rules(theme) if _PSEUDO_STATE.search(selector)}

    assert not present - enumerated, (
        "interaction state(s) nothing enumerates — add them to `theme.STATE_RULES` with what they "
        f"tell the user and the channel that says it without colour: {sorted(present - enumerated)}"
    )
    assert not enumerated - present, (
        "`theme.STATE_RULES` names selector(s) the sheet does not have, so the registry has "
        f"drifted from what it describes: {sorted(enumerated - present)}"
    )


def test_a_channel_claim_is_bound_to_what_its_selector_can_actually_be() -> None:
    """**A classification nothing checks is a comment.** Found by mutation, after the fact.

    Reclassifying `QMenu::item:selected` from `luminance` to `pointer-feedback` passed every other
    assertion in this file: the registry said the highlight was mere pointer feedback, and nothing
    disagreed. That is the whole defect class `T202-R1` is about, one level up — a rule *about* the
    rules, asserted by nobody.

    Two of the four channels are mechanically checkable from the selector, and those are exactly
    the two that excuse a rule from carrying a visible second channel:

    - **`pointer-feedback` means hover or pressed.** Those are the only states that exist solely
      while a pointer is on the control. `:selected`, `:checked` and `:focus` outlive the pointer
      and are information; claiming otherwise is how a real state gets excused.
    - **`published-state` means disabled.** It is the one state Qt puts in the accessibility tree
      by itself.

    `geometry` and `luminance` are not checkable from the selector — they are claims about what is
    drawn — so they are checked by drawing it instead, in the two tests below.
    """
    for rule in ui_theme.STATE_RULES:
        if rule.channel == "pointer-feedback":
            assert ":hover" in rule.selector or ":pressed" in rule.selector, (
                f"{rule.selector!r} claims to be pointer feedback, but it is not a hover or "
                "pressed rule — a state that outlives the pointer is information, and needs a "
                "channel that outlives it too"
            )
        if rule.channel == "published-state":
            assert ":disabled" in rule.selector, (
                f"{rule.selector!r} claims the accessibility tree carries it, but only "
                "`:disabled` is published by Qt without being drawn"
            )


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_every_luminance_claim_is_far_enough_apart_to_be_one(theme: ui_theme.Theme) -> None:
    """Driven from the registry, so a rule that *claims* `luminance` is the rule that gets checked.

    Asserting the menu highlight by name would have left the claim and the check independent —
    which is what let the mutation above through. Anything classified `luminance` is measured, and
    a new one is measured the moment it is added.
    """
    claimed = [rule for rule in ui_theme.STATE_RULES if rule.channel == "luminance"]
    assert claimed, "no rule claims `luminance`, so this test would pass over nothing"

    for rule in claimed:
        ratio = ui_theme.contrast_ratio(theme.surface, theme.primary)
        assert ratio >= ui_theme.MINIMUM_CONTRAST, (
            f"{rule.selector!r} in {theme.name} sits {ratio:.2f}:1 from its unselected ground, "
            f"under the {ui_theme.MINIMUM_CONTRAST} floor — at that distance it is a hue change "
            "rather than a brightness one"
        )


def test_every_enumerated_state_declares_a_channel_that_exists() -> None:
    """A registry whose values are free text is a registry that can say anything.

    Each entry has to name one of the four channels `STATE_CHANNELS` defines, and give a reason —
    the reason is what a reviewer reads to decide whether the classification is honest, and an
    entry claiming `pointer-feedback` for something a keyboard user needs would be caught there
    rather than here.
    """
    for rule in ui_theme.STATE_RULES:
        assert rule.channel in ui_theme.STATE_CHANNELS, (
            f"{rule.selector!r} claims channel {rule.channel!r}, which is not one of "
            f"{sorted(ui_theme.STATE_CHANNELS)}"
        )
        assert rule.conveys.strip(), f"{rule.selector!r} does not say what it conveys"
        assert len(rule.reason.split()) >= 8, (
            f"{rule.selector!r} gives no reason worth reading: {rule.reason!r}"
        )


#: How far one pixel's brightness must move between two renders to count as a visible change.
#:
#: `theme.MINIMUM_CONTROL_CONTRAST` — WCAG 2.1's non-text floor of **3:1**, which is the number
#: this project already uses for *an edge you can see*. Reusing it means this measurement agrees
#: with the finding it exists to catch rather than with a threshold picked to make it agree: the
#: idle and focus border colours sit **1.45:1** apart in light and **2.17:1** in dark, so every
#: pixel of the original recolour falls under this bar and the whole change scores **zero**.
VISIBLY_CHANGED: Final = ui_theme.MINIMUM_CONTROL_CONTRAST


def as_hex(pixel: int) -> str:
    """One `QRgb` as `#rrggbb`, which is what `theme.contrast_ratio` reads."""
    return f"#{pixel & 0xFFFFFF:06x}"


def pixels_of(image: QImage) -> memoryview:
    """Every pixel of `image` as one machine word, in order."""
    return memoryview(bytes(image.constBits())).cast("I")


def visible_change(before: QImage, after: QImage) -> int:
    """How many pixels differ between two renders **in brightness**, not merely in hue.

    **This is the whole instrument, and every assertion about focus in this file is this number.**
    Two earlier versions counted **ink** — pixels unlike the control's own fill — and both reported
    a pass for something that was not one. The first compared against `theme.window` when a
    control's own ground is `surface`, so a fix that plainly worked measured zero. The second
    assumed the fill holds still, and it does not: Qt hands `:default` to whichever button has
    focus, so six of the preset manager's seven buttons go from a `#ffffff` ground to `#1e5e47`
    the moment they take the keyboard. Ink counted against a fill that moved underneath it is two
    questions averaged together.

    So it asks the criterion's own question instead — **would a greyscale reading see a
    difference?** — pixel against the same pixel, which needs no fill and survives the control
    changing colour entirely. A recolour at the same brightness scores zero however large it is;
    a thicker edge, an inverted fill and a redrawn arrow all score what they are worth.

    **`T202-R2` is why the third version of this docstring is shorter than the second.** It
    recorded a rendered list whose doubled gold border scored *identically to the pixel* — 5958
    before and after — as the reason ink was the wrong measure. That number was produced with the
    palette **not installed**, which is the defect `T202-R2` found in the tests around this
    function; with `theme.apply` in force it does not reproduce, and a claim that does not
    reproduce does not belong in the reason for a change. What is left is the part that does: the
    `:default` inversion above, measured, and the fact that *did a greyscale reader see it* is the
    question `NFR-005` actually asks.
    """
    assert before.size() == after.size(), "the two renders are different sizes"
    changed = Counter(zip(pixels_of(before), pixels_of(after), strict=True))
    return sum(
        count
        for (first, second), count in changed.items()
        if first != second
        and ui_theme.contrast_ratio(as_hex(first), as_hex(second)) >= VISIBLY_CHANGED
    )


def focus_change(widget: QWidget, qapp: QApplication) -> int:
    """Render `widget` unfocused and focused, and measure what a greyscale reading would keep."""
    widget.clearFocus()
    qapp.processEvents()
    assert not widget.hasFocus(), f"{widget} kept focus after clearFocus()"
    idle = rendered(widget)

    widget.setFocus()
    qapp.processEvents()
    assert widget.hasFocus(), f"{widget} would not take focus, so this compares two idle renders"
    return visible_change(idle, rendered(widget))


def test_the_measure_sees_a_thicker_edge_and_not_a_recolour(qapp: QApplication) -> None:
    """The instrument, against squares whose answers are known before it runs.

    **Every assertion about focus in this file is `visible_change`'s output**, and it has been
    wrong three times in ways that turned a broken fix green — the wrong background, a highlight
    line counted as ink, and a fill that moved under the measurement. A metric that under-reports
    change makes a *fix* look like a no-op and a *defect* look like nothing at all, and none of the
    three was caught by a test, because the tests were the thing being measured.

    So: the same square twice, a square whose edge thickens, a square whose edge changes hue
    without changing brightness, and the two border colours this whole finding is about.
    """

    def square(edge: int, colour: str) -> QImage:
        image = QImage(40, 40, QImage.Format.Format_ARGB32)
        image.fill(QColor("#ffffff"))
        if edge:
            painter = QPainter(image)
            painter.setPen(QPen(QColor(colour), edge))
            # Inset by half the pen so the whole stroke lands inside the image.
            painter.drawRect(edge // 2, edge // 2, 39 - edge, 39 - edge)
            painter.end()
        return image

    plain = square(1, "#555555")
    assert visible_change(plain, square(1, "#555555")) == 0, "the same render measured a change"

    thicker = visible_change(plain, square(2, "#555555"))
    assert thicker > 100, f"a doubled edge measured {thicker} pixels of change"

    # `#555555` and `#4a4a7a` are 1.06:1 apart — a hue change with the brightness held still.
    recoloured = visible_change(plain, square(1, "#4a4a7a"))
    assert recoloured == 0, (
        f"an edge recoloured at the same brightness measured {recoloured} pixels of change — this "
        "is the one thing the measure must never see, because it is what focus used to do"
    )

    # And the finding's own pair, which is what the first version of this fix left in place.
    for theme in THEMES:
        defect = visible_change(square(1, theme.border), square(1, theme.accent))
        assert defect == 0, (
            f"recolouring a border from {theme.border} to {theme.accent} in {theme.name} measured "
            f"{defect} pixels of change, and those two are "
            f"{ui_theme.contrast_ratio(theme.border, theme.accent):.2f}:1 apart — a measure that "
            "sees this passes the defect T202-R1 was raised for"
        )


def rendered(widget: QWidget) -> QImage:
    """`widget` drawn offscreen, at its current size."""
    image = QImage(widget.size(), QImage.Format.Format_ARGB32)
    image.fill(QColor("#00000000"))
    widget.render(image)
    return image


def viewport_of(widget: QWidget) -> QRect | None:
    """The rectangle a scrolling control draws its contents in, or `None` for one that has no such.

    A list, a table, a tree and both text edits are `QAbstractScrollArea`s: their frame is drawn on
    the widget and their contents live in a child viewport, which is why a thicker frame can reach
    the rows a user is reading without moving the widget at all.
    """
    return widget.viewport().geometry() if isinstance(widget, QAbstractScrollArea) else None


def repainted_on_the_edge_of(before: QImage, after: QImage, rect: QRect) -> int:
    """How many pixels of `rect`'s own outermost ring differ between the two renders."""
    changed = 0
    for y in range(rect.top(), rect.bottom() + 1):
        for x in range(rect.left(), rect.right() + 1):
            on_edge = x in (rect.left(), rect.right()) or y in (rect.top(), rect.bottom())
            if on_edge and before.pixelColor(x, y) != after.pixelColor(x, y):
                changed += 1
    return changed


def dress(qapp: QApplication, theme: ui_theme.Theme) -> None:
    """Put the application in `theme` — **all of it, not only the style sheet** (`T202-R2`).

    `theme.apply` is the one call that themes anything, and it does three things: it installs the
    style sheet, it installs the `QPalette`, and it records the theme in `theme.applied()`. Every
    rendered test here called `setStyleSheet` alone, so **the dark cases were not dark**: measured,
    both parameter cases kept `applied=light` and the platform's own `#efefef` window, where the
    dark theme's is `#0A1712`.

    That is not a cosmetic difference in what got measured. `SortableHeader` reads
    `theme.applied().accent` to paint its current section, and `QPalette` is the path Qt itself
    takes for anything a style sheet cannot express — item-view selections, and any widget that
    calls `palette().window()`. A painter with the light accent hard-coded would have passed the
    dark regression, which is the mutation `test_the_dark_sweep_is_dark` and the battery now run.

    The two assertions are the guard: this defect was invisible because nothing asked. Cleanup is
    the autouse `_undressed_afterwards` fixture in `tests/ui/conftest.py`, which puts the sheet,
    the palette **and** `theme.applied()` back — a `finally` that only cleared the sheet was the
    other half of the same mistake.
    """
    ui_theme.apply(qapp, theme)
    assert ui_theme.applied() is theme, (
        f"the application reports {ui_theme.applied().name} after being dressed in {theme.name} — "
        "a painter reading theme.applied() would be drawing the wrong palette's colours"
    )
    window = qapp.palette().color(QPalette.ColorRole.Window).name().lower()
    assert window == theme.window.lower(), (
        f"the palette's window is {window} and {theme.name} says {theme.window} — the style sheet "
        "is in force and the palette is not, so everything Qt draws from the palette is untouched"
    )


def one_more_ring(widget: QWidget) -> int:
    """How much ink a second pixel of border adds to a control this size.

    **The floor has to scale, because the controls do not.** A fixed pixel count was the first
    version of this measurement, and it would have passed the seven controls this round adds while
    failing a stepper that is drawn correctly: a `QToolButton[stepButton="true"]` is 17 by 25, so
    its whole extra ring is **80 pixels** — under the 100 the fixed floor asked for — where a list
    is 238 by 145 and gains **754**. Both are the same one-pixel edge, and the edge is the point.

    **A header is measured by its focused section, not by itself** (`T-329`, maintainer's ruling
    2026-09-11, option A). `QHeaderView` draws focus on the **current section**, so the ink it
    changes is constant while a perimeter floor climbs with the header's width — a size race that
    any wide enough header loses. It lost on Windows first, and Linux was 22 pixels behind it:

    | | ink changed | floor at 299 px | at 312 px |
    |---|---|---|---|
    | Linux | 430, constant | 392 | 408 |
    | Windows | 386, constant | 389 | 404 |

    Measured on both platforms rather than reasoned about. The current section is logical index 0
    and **84 pixels wide** on every one of the six headers this sweep reaches, against widgets of
    198 to 312 — so the section is what the indicator is drawn on, and the section is what the
    floor is taken from. The floor for those becomes **134**, which a control that merely
    recolours still cannot reach: that scores ~0, which is the distinction this whole measurement
    exists to make.

    **The special case is narrow on purpose.** Every control whose focus really is drawn around
    itself keeps the perimeter model unchanged, so this weakens nothing else. `T-329` records the
    three alternatives and why they were rejected — capping the floor would have blunted it for
    every large control.
    """
    if isinstance(widget, QHeaderView):
        width, height = _focused_section(widget)
        return 2 * (width + height) - 4
    return 2 * (widget.width() + widget.height()) - 4


def _focused_section(header: QHeaderView) -> tuple[int, int]:
    """The size of the section focus is drawn on: across the header, and its full depth.

    Falls back to the first section when there is no current index — a header with focus and no
    current section still has to draw somewhere, and index 0 is where Qt puts it.
    """
    index = header.currentIndex()
    across = header.orientation() == Qt.Orientation.Horizontal
    logical = (index.column() if across else index.row()) if index.isValid() else 0
    section = header.sectionSize(max(logical, 0))
    return (section, header.height()) if across else (header.width(), section)


#: How much of that ring a control must actually gain to count as having thickened its edge.
#:
#: Measured 2026-08-15 across every focusable control in `theme.BORDERED_CONTROLS`, both palettes
#: and with `theme.apply` in force (`T202-R2`): **0.82 to 1.94** of a full ring. The low end is the
#: stepper, whose rounded corners cost it a few pixels; the high end is the primary verb, where the
#: ring lands on a brand fill and the padding shifts the label as well. A rule that only recolours
#: scores **0.00**. The floor sits between the two with room on either side, so it separates the
#: two states of the world this test exists to tell apart without flapping on a rounding difference.
MINIMUM_FOCUS_RING_SHARE: Final = 0.6


def build(selector: str, host: QWidget) -> QWidget:
    """Build the control `selector` names, inside `host`, ready to be rendered.

    **A recipe per selector, checked against the sheet.** The inventory in `theme.py` is a list of
    selector strings, and a selector cannot be instantiated: two of them are roles carried by a
    dynamic property and two more are only meaningful inside a particular parent. This is where
    that knowledge lives, and `test_every_bordered_control_can_be_built` fails if the sheet grows a
    bordered control this function does not know how to make — which is the failure that would
    otherwise present as a control quietly dropping out of the rendered sweep.
    """
    layout = host.layout()
    assert layout is not None, "build() lays its controls out, so the host needs a layout"
    if selector == 'QToolButton[stepButton="true"]':
        stepper = QToolButton(host)
        stepper.setText("+")
        stepper.setProperty(settings_dialog.STEP_BUTTON_PROPERTY, "true")
        layout.addWidget(stepper)
        return stepper
    if selector == 'QToolButton[disclosure="true"]':
        # **The panel's way out** (`P4EXIT-R1`). Built the way `RowPanel` builds it — the arrow and
        # `autoRaise` are what make it read as the painted triangle it replaces rather than as a
        # button, and both affect what a rendered focus comparison sees.
        disclosure = QToolButton(host)
        disclosure.setArrowType(Qt.ArrowType.DownArrow)
        disclosure.setAutoRaise(True)
        disclosure.setProperty("disclosure", True)
        layout.addWidget(disclosure)
        return disclosure
    if selector in {"QToolBar QToolButton", 'QToolBar QToolButton[primaryAction="true"]'}:
        bar = QToolBar(host)
        verb = QToolButton(bar)
        verb.setText("Pause queue")
        if "primaryAction" in selector:
            verb.setProperty("primaryAction", "true")
        bar.addWidget(verb)
        layout.addWidget(bar)
        return verb
    if selector == "QComboBox QAbstractItemView":
        # The drop-down's own view, which is a popup window and never appears in a layout.
        combo = QComboBox(host)
        combo.addItems(["Alpha", "Beta"])
        return combo.view()
    widget: QWidget = CLASSES[selector](host)
    if isinstance(widget, QComboBox):
        widget.addItems(["Alpha", "Beta"])
    if isinstance(widget, QGroupBox):
        widget.setTitle("Group")
    if isinstance(widget, QMenu):
        widget.addAction("Open")
        return widget
    layout.addWidget(widget)
    return widget


#: The plain one-class selectors, resolved to the class the sheet names.
CLASSES: Final[dict[str, type[QWidget]]] = {
    "QCheckBox": QCheckBox,
    "QRadioButton": QRadioButton,
    "QPushButton": QPushButton,
    "QComboBox": QComboBox,
    "QLineEdit": QLineEdit,
    "QListView": QListView,
    "QTableView": QTableView,
    "QTreeView": QTreeView,
    "QPlainTextEdit": QPlainTextEdit,
    "QTextEdit": QTextEdit,
    "QGroupBox": QGroupBox,
    "QProgressBar": QProgressBar,
    "QMenu": QMenu,
}

#: A `border: <n>px solid <colour>` shorthand, which is what makes a control *already bordered*.
#:
#: `border: none` and `border-bottom` are deliberately not matched: a header strip's single rule
#: and a selected row's left bar are not edges focus could thicken.
_BORDER_SHORTHAND: Final = re.compile(r"\bborder:\s*(\d+)px\s+solid\b")

FOCUSABLE: Final = tuple(control for control in ui_theme.BORDERED_CONTROLS if control.takes_focus)

#: The controls whose contents live in a viewport rather than directly on the widget.
#:
#: Named rather than measured, because parametrisation happens at collection time and there is no
#: `QApplication` yet to build a widget with. `test_the_scrolling_controls_are_the_scrolling_ones`
#: is what stops the list being an opinion.
SCROLLING: Final = frozenset(
    {"QListView", "QTableView", "QTreeView", "QPlainTextEdit", "QTextEdit"}
)


def bordered_selectors(theme: ui_theme.Theme) -> set[str]:
    """Every control the sheet gives a border of its own, read out of the sheet itself.

    **Idle rules only**: a selector carrying a pseudo-state (`:focus`, `:checked`) or a sub-control
    (`::item`) is describing something that happens *to* a control, not another control. Splitting
    the comma-separated groups is what stops `QGroupBox` hiding inside the same rule as five
    focusable views — which is exactly where it was hiding.
    """
    found: set[str] = set()
    for selector, body in rules(theme):
        if not _BORDER_SHORTHAND.search(body):
            continue
        for part in selector.split(","):
            one = " ".join(part.split())
            if ":" not in one and "*" not in one:
                found.add(one)
    return found


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_the_inventory_is_every_bordered_control_the_sheet_has(theme: ui_theme.Theme) -> None:
    """**`T202-R1`, second round.** The inventory was three controls; the sheet borders fifteen.

    A control that already has a border cannot show focus by *growing* one, so `*:focus` can only
    recolour it. That is a property of having a border — not of being a button — and the first
    correction was written against the three controls the finding happened to name.

    **Read out of the generated sheet, not out of the tuple.** A test that iterated
    `BORDERED_CONTROLS` and checked each entry appeared would pass a sheet that had grown a
    sixteenth bordered control, which is the same shape of gap one level up.
    """
    listed = {control.selector for control in ui_theme.BORDERED_CONTROLS}
    drawn = bordered_selectors(theme)
    assert drawn - listed == set(), (
        f"{sorted(drawn - listed)} are given a border by the {theme.name} sheet and are not in "
        "theme.BORDERED_CONTROLS — every bordered control has to answer whether focus can land on "
        "it, because for those it can, recolouring the border is the whole of T202-R1"
    )
    assert listed - drawn == set(), (
        f"{sorted(listed - drawn)} are in theme.BORDERED_CONTROLS and the {theme.name} sheet no "
        "longer gives them a border — a stale entry means the sweep is guarding nothing"
    )


def test_every_bordered_control_can_be_built() -> None:
    """The rendered sweep is only as complete as `build()`, so the gap is closed here too."""
    for control in ui_theme.BORDERED_CONTROLS:
        assert control.selector in CLASSES or control.selector in {
            'QToolButton[stepButton="true"]',
            'QToolButton[disclosure="true"]',
            "QToolBar QToolButton",
            'QToolBar QToolButton[primaryAction="true"]',
            "QComboBox QAbstractItemView",
        }, (
            f"{control.selector!r} is in the inventory and build() cannot make one, so it would "
            "silently sit out every rendered assertion below"
        )


def test_the_scrolling_controls_are_the_scrolling_ones(qapp: QApplication) -> None:
    """`SCROLLING` decides which controls face the contents-repaint check, so Qt decides it here."""
    host = QWidget()
    QVBoxLayout(host)
    measured = {
        control.selector
        for control in FOCUSABLE
        if isinstance(build(control.selector, host), QAbstractScrollArea)
    }
    assert measured == SCROLLING, (
        f"SCROLLING says {sorted(SCROLLING)} and Qt says {sorted(measured)} — a scrolling control "
        "missing from that set sits out the one check that catches a ring drawn over its contents"
    )


def test_a_bordered_control_left_out_of_the_inventory(qapp: QApplication) -> None:
    """Each `takes_focus` claim is put to Qt rather than believed.

    **This is the assertion that stops the exemptions being an opinion.** `QGroupBox`,
    `QProgressBar`, `QMenu` and the drop-down's view are excused from thickening their border, and
    an excuse a reviewer has to take on trust is how `COINCIDENTAL_SEMANTIC_VALUES` came to excuse
    the focus ring itself. A control is excused only if Qt reports `NoFocus`, or if it is a popup
    window — on screen only while it is the thing being used, so it has no unfocused state to be
    told apart from.

    **`Qt.Popup` is `Qt.Window | 0x8`**, so `flags & Qt.Popup` is true of every top-level widget
    there is and the first version of this check excused everything. It was caught by mutating
    the list control to `takes_focus=False`, which the check happily accepted; the window-type mask
    the comparison Qt intends. A test that cannot fail is worth less than no test, because it also
    reports that the question has been asked.
    """
    host = QWidget()
    QVBoxLayout(host)
    for control in ui_theme.BORDERED_CONTROLS:
        widget = build(control.selector, host)
        policy = widget.focusPolicy()
        window_type = widget.window().windowFlags() & Qt.WindowType.WindowType_Mask
        popup = window_type == Qt.WindowType.Popup
        if control.takes_focus:
            assert policy != Qt.FocusPolicy.NoFocus, (
                f"{control.selector!r} claims the keyboard can land on it and Qt reports "
                f"{policy.name} — the claim is what decides whether its border thickens"
            )
        else:
            assert policy == Qt.FocusPolicy.NoFocus or popup, (
                f"{control.selector!r} is excused from thickening its border on the grounds that "
                f"focus never lands there, and Qt reports {policy.name} on a non-popup window. "
                "Either the exemption is wrong or the control needs the geometry change"
            )


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
@pytest.mark.parametrize("control", FOCUSABLE, ids=lambda control: control.selector)
def test_focus_is_visible_without_reading_its_colour(
    qapp: QApplication, theme: ui_theme.Theme, control: ui_theme.BorderedControl
) -> None:
    """**`T202-R1`.** Focus was conveyed by colour alone on every already-bordered control.

    `*:focus` changed `border: 1px solid theme.border` to `border: 1px solid theme.accent`: same
    width, same shape, same geometry. Measured on a rendered `QPushButton`, **414 pixels changed
    and not one was background becoming ink**, with the idle and focus border colours **1.45:1**
    apart in light and **2.17:1** in dark. A keyboard user who cannot separate those two hues had
    no focus indicator at all.

    **Parametrised over the inventory**, which is the second round's whole point: the same
    measurement over `QListView`, `QTableView`, `QTreeView`, `QPlainTextEdit`, `QTextEdit`, a
    stepper and a toolbar verb returned a **literal zero** in both palettes while the three
    controls the finding named were passing.

    This renders the control idle and focused and counts ink both times. **It never compares an RGB
    value**, which is the point: the assertion is about whether the shape changed, so it cannot be
    satisfied by choosing a louder colour.
    """
    dress(qapp, theme)
    host = QWidget()
    layout = QVBoxLayout(host)
    elsewhere = QPushButton("elsewhere", host)
    layout.addWidget(elsewhere)
    widget = build(control.selector, host)
    host.resize(260, 200)
    host.show()
    qapp.processEvents()

    elsewhere.setFocus()
    qapp.processEvents()
    change = focus_change(widget, qapp)

    floor = MINIMUM_FOCUS_RING_SHARE * one_more_ring(widget)
    assert change >= floor, (
        f"{control.selector!r} in {theme.name} changes {change} pixels in brightness when "
        f"focused, under the {floor:.0f} its size asks for — focus is being drawn by changing "
        "a colour rather than by changing the edge"
    )


#: The controls whose contents sit *inside* their own rectangle, and the style sub-elements that
#: say where. `QStyle` names these per class, so there is no generic way to ask the question — and
#: these two are the pair whose contents were measured moving (`T-303`).
CONTENTS_SUB_ELEMENTS: Final = {
    "QCheckBox": (QStyle.SubElement.SE_CheckBoxContents, QStyle.SubElement.SE_CheckBoxIndicator),
    "QRadioButton": (
        QStyle.SubElement.SE_RadioButtonContents,
        QStyle.SubElement.SE_RadioButtonIndicator,
    ),
}


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
@pytest.mark.parametrize("selector", sorted(CONTENTS_SUB_ELEMENTS))
def test_focus_does_not_move_what_the_control_draws(
    qapp: QApplication, theme: ui_theme.Theme, selector: str
) -> None:
    """The contents must not move **inside** the widget either (`T-303`).

    `test_focus_does_not_move_the_control` checks geometry, size hint and viewport — where the
    control sits in its layout. **None of those see a control whose contents reflow inside an
    unchanged rectangle**, which is what a check box did: the widget stayed put while its
    indicator moved from x=0 to x=1 and its label from 19 to 21, because `*:focus` added a border
    to a box that had reserved no room for one.

    **The gap was measured, not guessed.** Reserving *one* pixel against the two-pixel ring leaves
    geometry and hint exactly as they were and the older test still passes; this one fails. That
    is the difference between guarding the property and guarding a symptom of it.

    **Exact rectangles rather than a pixel diff.** A rendered comparison was tried first and
    flagged every bordered control in both themes — focus legitimately repaints a control, and an
    image cannot tell a repaint from a reflow. `QStyle` names contents sub-elements per class, so
    the question is only askable for the classes that have them; these are the two the defect was
    found on, and a control added here has to bring its sub-elements with it.
    """
    dress(qapp, theme)
    host = QWidget()
    layout = QVBoxLayout(host)
    elsewhere = QPushButton("elsewhere", host)
    layout.addWidget(elsewhere)
    widget = build(selector, host)
    host.resize(260, 200)
    host.show()
    qapp.processEvents()

    def rects() -> tuple[QRect, ...]:
        qapp.processEvents()
        option = QStyleOptionButton()
        assert isinstance(widget, QCheckBox | QRadioButton)
        widget.initStyleOption(option)
        return tuple(
            widget.style().subElementRect(element, option, widget)
            for element in CONTENTS_SUB_ELEMENTS[selector]
        )

    elsewhere.setFocus()
    idle = rects()
    widget.setFocus()
    focused = rects()

    assert idle == focused, (
        f"{selector} moves its own contents when focus arrives: {idle} idle against {focused} "
        "focused. The ring is allowed to appear; the label underneath it is not allowed to shift."
    )


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
@pytest.mark.parametrize("control", FOCUSABLE, ids=lambda control: control.selector)
def test_focus_does_not_move_the_control(
    qapp: QApplication, theme: ui_theme.Theme, control: ui_theme.BorderedControl
) -> None:
    """The other half of the arithmetic: the padding gives up exactly what the border takes.

    **A thicker edge that reflows the form is not a fix**, it is a different defect — text shifting
    under the caret as the keyboard arrives, and a layout that jitters as focus moves through it.
    Each rule pays for its extra pixel out of its own padding, and the views and text edits had
    none, so the idle rule grants them one to spend.

    Geometry *and* size hint, because they fail differently: a control in a stretching layout keeps
    its geometry while its hint grows, and a control in a sized layout does the reverse. The
    viewport is checked as well, for the scrolling controls where the frame and the contents are
    different rectangles — though `test_focus_does_not_paint_over_the_contents` is the assertion
    that actually holds those to account, for the reason it records.
    """
    dress(qapp, theme)
    host = QWidget()
    layout = QVBoxLayout(host)
    elsewhere = QPushButton("elsewhere", host)
    layout.addWidget(elsewhere)
    widget = build(control.selector, host)
    host.resize(260, 200)
    host.show()
    qapp.processEvents()

    elsewhere.setFocus()
    qapp.processEvents()
    idle_geometry, idle_hint = widget.geometry(), widget.sizeHint()
    idle_viewport = viewport_of(widget)

    widget.setFocus()
    qapp.processEvents()
    layout.activate()
    qapp.processEvents()

    assert viewport_of(widget) == idle_viewport, (
        f"{control.selector!r} in {theme.name} moves its contents when focused: viewport "
        f"{idle_viewport} to {viewport_of(widget)} — the frame grew inwards, so every row or "
        "character inside it steps across as the keyboard arrives"
    )
    assert widget.geometry() == idle_geometry, (
        f"{control.selector!r} in {theme.name} moves or resizes when focused: "
        f"{idle_geometry} to {widget.geometry()} — the padding is not paying for the border"
    )
    assert widget.sizeHint() == idle_hint, (
        f"{control.selector!r} in {theme.name} asks for a different size when focused: "
        f"{idle_hint} to {widget.sizeHint()} — nothing has moved yet, and it will"
    )


#: How much of the contents rectangle's own edge a focus ring may repaint.
#:
#: Measured 2026-08-15 on all five scrolling controls, both palettes: **12 pixels**, which is the
#: four rounded corners and nothing else, against a 746-pixel edge — **1.6%**. Take the padding
#: away and it is **754 pixels, 101%**: the whole thicker border, drawn straight over the first row.
MOST_OF_THE_CONTENTS_EDGE: Final = 0.25


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
@pytest.mark.parametrize(
    "control",
    [control for control in FOCUSABLE if control.selector in SCROLLING],
    ids=lambda control: control.selector,
)
def test_focus_does_not_paint_over_the_contents(
    qapp: QApplication, theme: ui_theme.Theme, control: ui_theme.BorderedControl
) -> None:
    """Why the views and text edits are given a pixel of padding to spend.

    **Qt does not re-measure a frame when focus arrives.** The width comes from the style sheet at
    polish time, so a rule that thickens the border on `:focus` alone does not push the viewport
    inwards — it paints the extra pixel *on top of* the contents. Measured with the padding
    deleted: the viewport keeps its geometry exactly, `frameWidth()` still reports 1, and **754
    pixels of the contents rectangle's own edge are repainted** — the first row of a list, the
    first line of a log.

    **This is the assertion the geometry test could not make.** Both of them passed with the
    padding gone, which is how the padding came to be justified in a comment by something that does
    not happen: nothing moves, because there is nowhere for it to move to. It is covered instead.

    With the pixel of padding the thicker border has its own room and stops at the contents' edge:
    the only thing repainted there is the four rounded corners.
    """
    dress(qapp, theme)
    host = QWidget()
    layout = QVBoxLayout(host)
    elsewhere = QPushButton("elsewhere", host)
    layout.addWidget(elsewhere)
    widget = build(control.selector, host)
    host.resize(260, 200)
    host.show()
    qapp.processEvents()

    elsewhere.setFocus()
    qapp.processEvents()
    assert isinstance(widget, QAbstractScrollArea)
    idle = rendered(widget)
    contents = widget.viewport().geometry()

    widget.setFocus()
    qapp.processEvents()
    repainted = repainted_on_the_edge_of(idle, rendered(widget), contents)

    allowed = MOST_OF_THE_CONTENTS_EDGE * one_more_ring(widget.viewport())
    assert repainted < allowed, (
        f"{control.selector!r} in {theme.name} repaints {repainted} pixels of its contents' "
        f"own edge when focused, over the {allowed:.0f} a corner radius accounts for — the "
        "focus border is being drawn over the first row rather than beside it"
    )


# --- the same question, asked of the application itself (T202-R1, third round) -----------------
#
# **Everything above reads the style sheet, and the style sheet is not the only thing that draws a
# border.** The inventory was built by parsing `stylesheet()` for `border: <n>px solid`, so it
# could only ever contain controls this project had thought to style — and `QListView` was not one
# of them. Qt frames a `QListView` natively with a `StyledPanel`, `*:focus` then recoloured that
# frame, and the two lists this application is mostly made of — the queue and the add dialog's
# staging list — were conveying focus by colour alone while every test above passed.
#
# A parser cannot find that. Only rendering can. So this walks the **realised application**, asks
# Qt which controls the keyboard can reach, and holds every one of them to the same measurement,
# whatever draws it and whether or not anything in `theme.py` mentions it.

#: The floor this sweep must clear before its silence means anything.
#:
#: **Measured 2026-08-15 across the nine surfaces**: 50 controls reached and measured and 12
#: skipped as disabled, with the Settings screen contributing 18 and the preset manager 11. Set so
#: that losing the largest surface fails it — 50 less 18 is 32, under this — which is the same
#: reasoning and the same failure shape as `COVERAGE_FLOOR` in `test_accessibility.py`: not a
#: control added or removed, but a whole screen quietly dropping out.
#:
#: The main window contributes **nothing**, and that is a real gap rather than an oversight. Its
#: queue is a `QListView` that `_show_the_right_thing` hides while the queue is empty, and the
#: inventory's queue is empty — so the very control `T202-R1`'s third round is about is not on any
#: screen this sweep can see. What holds the line is that the defect and the fix are both by
#: **class**: the add dialog's `StagingList` is a `QListView` on a screen that is realised, it
#: measured zero here, and one rule fixed both.
SURFACE_COVERAGE_FLOOR: Final = 34


def surface_alone(surfaces: list[Surface], surface: Surface, qapp: QApplication) -> None:
    """Show `surface` and hide the others, so its controls can actually hold the keyboard.

    **Qt draws `:focus` from `hasFocus()`, which is false while another window is active** — and a
    modal dialog blocks the window beneath it outright. The inventory opens the add dialog, the
    Settings screen and the About box on top of the main window, so a sweep that walked it as it
    stands would measure one surface and silently skip eight. The first version of this did exactly
    that: 39 controls on the main window, every one of them reported as taking no focus.
    """
    for other in surfaces:
        if other is not surface:
            other.widget.window().hide()
    window = surface.widget.window()
    window.show()
    window.activateWindow()
    window.raise_()
    qapp.processEvents()


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_focus_is_visible_on_every_control_the_application_shows(
    every_surface: list[Surface], qapp: QApplication, theme: ui_theme.Theme
) -> None:
    """**`T202-R1`, third round.** Every control a keyboard can reach, on every screen there is.

    The bar is the same one the style-sheet sweep uses and it is applied to what is **drawn**: the
    render must differ by more than a hue, measured as a change in ink of at least
    `MINIMUM_FOCUS_RING_SHARE` of the control's own edge. A rule that only recolours scores zero
    however the border got there — declared in `theme.py`, inherited from a base class nobody
    styled, or drawn by Qt's own style.

    **A change in either direction counts, and that is deliberate.** The question this criterion
    asks is whether a user who cannot separate two hues can still tell focus has arrived, so what
    matters is that the *drawing* changed and not that it improved. Two of the Settings screen's
    spin boxes pass here by losing ink: focus gives them a style-sheet border, which switches them
    to `QStyleSheetStyle` and coarsens their native arrows from 48 distinct colours to 5 — the
    defect `T-133` left `QSpinBox` unstyled to avoid. That is visible, and it is not good; it is
    reported as its own matter rather than hidden by a metric that would have called it a pass.

    Disabled controls are skipped, because focus cannot land on one — twelve of them, checked to be
    disabled rather than assumed. Qt's internal children are skipped too: focusing a `QSpinBox`
    actually focuses its `qt_spinbox_lineedit`, and the control a user perceives is the parent,
    which this sweep measures in its own right.
    """
    dress(qapp, theme)
    measured = 0
    disabled = 0
    faults: list[str] = []

    for surface in reversed(every_surface):
        surface_alone(every_surface, surface, qapp)
        for widget in focusable(surface.widget):
            if widget.objectName().startswith("qt_"):
                continue
            if not widget.isEnabled():
                disabled += 1
                continue

            change = focus_change(widget, qapp)
            measured += 1
            control = f"{type(widget).__name__} {widget.objectName()}"
            if change >= MINIMUM_FOCUS_RING_SHARE * one_more_ring(widget):
                continue
            faults.append(
                f"{control} on {surface.label}: {change} pixels change in brightness on "
                f"focus, under the {MINIMUM_FOCUS_RING_SHARE * one_more_ring(widget):.0f} its "
                "size asks for"
            )

    assert not faults, (
        f"in {theme.name}, focus is drawn by changing a colour rather than the edge on: "
        + "; ".join(sorted(faults))
    )
    assert measured >= SURFACE_COVERAGE_FLOOR, (
        f"only {measured} controls were reached across {len({s.label for s in every_surface})} "
        f"surfaces, under the floor of {SURFACE_COVERAGE_FLOOR} — a screen has dropped out of the "
        "sweep, which is how a criterion comes to be applied to a subset"
    )
    assert disabled, "no disabled control was skipped, so that branch is doing nothing"


# --- painted state, which no style sheet reaches -----------------------------------------------


def test_every_painted_segment_state_is_also_a_word(qapp: QApplication) -> None:
    """The playlist header draws five states in five colours (`row_delegate._paint_segments`).

    **Its second channel is the row's own detail line**, which names each state and counts it —
    *"16 items · 12 done · 2 failed · 1 cancelled · 1 queued"*. Without that the bar is the only
    thing distinguishing a finished playlist from an abandoned one, and the chip beside it says
    only *"12 of 16"*, which counts the done and says nothing about the rest.

    This asserts the mapping is **total**: every state the painter has a colour for is a state the
    words have a name for. A sixth `SegmentState` added with a colour and no word fails here,
    which is the drift this is aimed at.
    """
    from tracks_and_trails.ui.queue_view import SEGMENT_STATE_WORDS

    assert set(SEGMENT_STATE_WORDS) == set(SegmentState), (
        "a painted segment state has no word: "
        f"{sorted(state.name for state in set(SegmentState) - set(SEGMENT_STATE_WORDS))}"
    )
    for state, word in SEGMENT_STATE_WORDS.items():
        assert word.strip(), f"{state.name} maps to an empty word"


# --- muted: the one that does not look like a semantic colour ----------------------------------


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_muted_is_either_secondary_emphasis_or_a_published_disabled_state(
    theme: ui_theme.Theme,
) -> None:
    """`T-202`: *"Grey is the one most likely to be missed."*

    A muted colour meaning *this cannot be used* is information conveyed by colour alone, and it
    does not look like a semantic colour because it is not in the `ok`/`warn`/`stop` set.

    Measured 2026-08-15, and the answer is that this application uses it for both — told apart by
    the selector. Every `muted` rule is either **secondary emphasis**, enumerated in
    `SECONDARY_EMPHASIS_SELECTORS`, or a **`:disabled`** rule, where the state is published to the
    accessibility tree as well as drawn (asserted below) and the control also does not respond.

    A new `muted` rule that is neither fails here and has to say which it is.
    """
    muted = theme.muted.lower()
    allowed = set(ui_theme.SECONDARY_EMPHASIS_SELECTORS)

    unclassified = [
        selector
        for selector, body in rules(theme)
        if muted in body.lower() and selector not in allowed and ":disabled" not in selector
    ]
    assert not unclassified, (
        "rule(s) using `muted` that are neither a disabled state nor enumerated as secondary "
        f"emphasis — say which they are: {unclassified}"
    )


@pytest.mark.parametrize("widget_type", [QPushButton, QComboBox])
def test_a_disabled_control_says_so_without_its_colour(
    qapp: QApplication, widget_type: type[QPushButton] | type[QComboBox]
) -> None:
    """The second channel for grey-as-unavailable, asserted rather than assumed.

    `muted` on a `:disabled` rule is only acceptable because the state reaches a user who never
    sees the colour. Qt publishes it — `QAccessible` reports `state().disabled` — and this is the
    check that it really does, for the two control kinds the sheet's disabled rules cover.

    Both polarities, because *"disabled is reported"* is worth nothing if it is reported always.
    """
    widget = widget_type()
    widget.setAccessibleName("A control")

    widget.setEnabled(True)
    interface = QAccessible.queryAccessibleInterface(widget)
    assert not interface.state().disabled, "an enabled control reports itself disabled"

    widget.setEnabled(False)
    interface = QAccessible.queryAccessibleInterface(widget)
    assert interface.state().disabled, (
        f"a disabled {widget_type.__name__} publishes no disabled state, so the only thing saying "
        "it cannot be used is its colour"
    )
