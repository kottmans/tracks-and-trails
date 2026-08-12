"""Brand palette and light/dark theming (`T-120`, `ARCHITECTURE.md` §8).

This file was one line — its own docstring — from Phase 0 until now, and nothing imported it. The
palette has been specified since `T-003` and never applied, so the application has been showing
whatever Qt's default style chose.

## The swatches are adopted, not measured

`ARCHITECTURE.md` §8 is explicit and `T003-R1` is why: the artwork contains no flat fills — each
coloured region is a cloud spanning roughly ±2 per channel — so clustering it recovers a different
centre for every reasonable algorithm and radius. **These three values are the definition; the
logo is their origin, not their proof.** Do not re-derive them from `icon.png`, and do not cite a
measurement as evidence for them. Changing one is a brand decision.

## Two themes, neither an inversion of the other

A dark theme built by inverting a light one produces a muddy accent and text that is technically
legible and unpleasant to read. Each theme names its own values, and `test_theme.py` asserts the
contrast of every text-on-ground pair in both rather than spot-checking one.

## Colour is never the signal

`NFR-005`, and it is the reason the semantic colours below are separate from the accent. A status
is conveyed by its **words**; `ok`, `warn` and `stop` exist to reinforce text that already says
what happened, never to replace it. A widget that sets one of these and no text is a defect this
palette cannot prevent and the tests for that widget must.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from PySide6.QtGui import QPalette

#: The project's canonical swatches (`ARCHITECTURE.md` §8, `T-003`, corrected by `T-022`).
#:
#: Named rather than inlined so the two themes below quote one source. A theme that wrote
#: `#1E5E47` itself would be a second place for the brand to live, and the first thing to drift.
FOREST: Final = "#1E5E47"
GOLD: Final = "#D9A24C"
DEEP: Final = "#083122"

#: The contrast floor for body text, from WCAG 2.1 AA at normal sizes.
#:
#: Stated as a number this project asserts against rather than as a standard it gestures at:
#: `NFR-005` requires the interface to be usable, and "usable" needs a threshold something can
#: fail. Large text and non-text controls have lower floors in the standard; this applies the
#: stricter one everywhere rather than classifying each widget, because the classification is the
#: part that rots.
MINIMUM_CONTRAST: Final = 4.5

#: The floor for a control's edge against the surface behind it — a border or a focus ring.
#: WCAG 2.1's non-text contrast requirement.
#:
#: **A divider is deliberately not one of these.** It encloses nothing and carries no meaning, and
#: drawing every gridline at 3:1 turns a quiet list into a grid of cages. `Theme.rule` is that
#: hairline; `Theme.border` is the edge of something you can operate, and only the second has a
#: floor. The split exists because the first version of this palette used one colour for both and
#: failed this check in **both** themes.
MINIMUM_CONTROL_CONTRAST: Final = 3.0


@dataclass(frozen=True)
class Theme:
    """One complete set of colours. Frozen, because a half-applied theme is a rendering bug.

    Every field is a role rather than a colour: `surface` is "what a panel sits on", not "light
    grey". A widget asking for `theme.surface` keeps working when the theme changes, which is the
    whole point of naming them.
    """

    name: str

    #: The window behind everything.
    window: str
    #: Panels, lists and rows sitting on the window.
    surface: str
    #: A sunken area — an input, a well, a header strip.
    sunken: str
    #: Body text on `window` or `surface`.
    text: str
    #: Text that is deliberately quieter: captions, secondary detail.
    muted: str
    #: A hairline that separates without enclosing: a table gridline, a divider between sections.
    #: **Deliberately below the control floor.** WCAG's non-text contrast applies to boundaries
    #: that carry meaning; a divider carries none, and drawing one at 3:1 turns a quiet list into a
    #: grid of cages. `border` is the one that must be seen.
    rule: str
    #: The edge of something you can operate — a button, an input, a focus ring. Meets
    #: `MINIMUM_CONTROL_CONTRAST` against both `window` and `surface`, because a control whose
    #: boundary is invisible is a control you cannot find.
    border: str

    #: The brand primary, used for the one thing on a screen that matters most.
    primary: str
    #: Text drawn *on* `primary`.
    on_primary: str
    #: The brand accent. Used sparingly and never as the only signal.
    accent: str

    #: `primary` **under the pointer** (`T-147`).
    #:
    #: **A lighter fill, not a coloured ring.** A filled button hovered used to keep its fill and
    #: take an `accent` border, which measured **1.42:1 against the fill in light and 1.25:1 in
    #: dark** — too low to read as gold, so it read as a smudge. Brightening the accent instead
    #: would have fixed one theme and not the other: `#D9A24C` is 3.36:1 on the light theme's
    #: forest and 1.25:1 on the dark theme's already-light green, which is `T130-R1`'s shape
    #: exactly — a change that looks right in the context it was chosen in.
    #:
    #: Lightening the fill works in both, because it moves *with* whichever primary it is given.
    #: `on_primary` stays legible on it, and that pair is in the contrast gate.
    primary_hover: str

    #: A selected row (`T-130`, `UX-005`'s 2026-08-04 amendment).
    #:
    #: **A tint of `primary` over `surface`, not `primary` itself.** Filling the whole row with the
    #: brand colour passes contrast — it measured 7.64:1 — and still dominates a list, which on the
    #: History tab meant one finished download shouting over three others. The mockup uses a light
    #: tint and an inset bar, and the bar is what carries the emphasis the fill was over-spending.
    #: `on_selection` stays the ordinary text colour for the same reason: at this weight the row is
    #: still a row.
    selection: str
    on_selection: str

    #: Semantic colours. Separate from `accent` on purpose (`NFR-005`): these reinforce words,
    #: they do not replace them.
    ok: str
    warn: str
    stop: str


LIGHT: Final = Theme(
    name="light",
    window="#F5F7F4",
    surface="#FFFFFF",
    sunken="#EAEFE9",
    text="#101A14",
    muted="#5A6A60",
    rule="#D5DED7",
    border="#748A7E",
    primary=FOREST,
    on_primary="#FFFFFF",
    selection="#EBF1EE",
    on_selection="#101A14",
    accent="#8A6412",
    primary_hover="#467B68",
    ok="#14503C",
    warn="#7A5410",
    stop="#8C3D29",
)

#: **Not an inversion.** The forest green that carries a white label at `#1E5E47` cannot also be
#: readable text on a near-black ground, so the dark theme lifts the primary and desaturates the
#: accent rather than reusing the light values on a flipped background. `DEEP` becomes the window
#: it was always meant to shade.
#:
#: `primary` is `#57A888` rather than the `#4E9C7C` this started at, because `DEEP` on that
#: measured **4.33** against a floor of 4.5. Near enough to pass by eye, which is the entire
#: argument for asserting the number.
DARK: Final = Theme(
    name="dark",
    window="#0A1712",
    surface="#10201A",
    sunken="#0D1B15",
    text="#E7EFE9",
    muted="#9FB2A6",
    rule="#21382E",
    border="#547866",
    primary="#57A888",
    on_primary=DEEP,
    selection="#1D382E",
    on_selection="#E7EFE9",
    accent=GOLD,
    primary_hover="#75B89D",
    ok="#7FC7A6",
    warn=GOLD,
    stop="#E09480",
)

THEMES: Final = {theme.name: theme for theme in (LIGHT, DARK)}


def _channels(colour: str) -> tuple[int, int, int]:
    """`#RRGGBB` as three ints. Raises rather than guessing at anything else.

    **Strict about the `#`, and about there being exactly one.** This used `lstrip("#")` and a
    length check, which accepted `1E5E47` and `###1E5E47` alike — the docstring claimed to raise
    and did not. It matters beyond tidiness: a bare hex is not a colour string Qt accepts, so
    tolerating one here moves the failure from this function to `QColor`, where it renders as
    black and reports nothing.
    """
    if not colour.startswith("#") or len(colour) != 7:
        raise ValueError(f"{colour!r} is not a #RRGGBB colour")
    try:
        return int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16)
    except ValueError as bad:
        raise ValueError(f"{colour!r} is not a #RRGGBB colour") from bad


def relative_luminance(colour: str) -> float:
    """WCAG 2.1 relative luminance, from `0.0` to `1.0`.

    Pure and Qt-free so contrast can be asserted without a `QApplication`, and so the arithmetic
    that decides whether this palette is legible is not itself hidden behind a widget.
    """
    parts = []
    for value in _channels(colour):
        fraction = value / 255
        parts.append(
            fraction / 12.92 if fraction <= 0.04045 else ((fraction + 0.055) / 1.055) ** 2.4
        )
    red, green, blue = parts
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: str, background: str) -> float:
    """The WCAG contrast ratio between two colours, from `1.0` to `21.0`.

    Symmetric, as the standard defines it — the lighter of the pair is the numerator whichever
    argument it arrived in — so a test cannot pass by putting the colours the other way round.
    """
    first = relative_luminance(foreground)
    second = relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def stylesheet(theme: Theme) -> str:
    """The theme as Qt style sheet text.

    **A style sheet rather than only a `QPalette`.** `QPalette` cannot express a border, a radius
    or a header strip, so a palette-only theme leaves half the surface at the platform default and
    the result reads as two designs at once. The palette is set as well, because a widget that
    reads `palette().window()` directly — and Qt has several — must agree with what is drawn.

    Selectors are by class, not by object name, so **a widget added without asking for a colour
    inherits the theme**. Naming widgets individually is how a new panel ends up the only grey
    thing on the screen.
    """
    return f"""
QWidget {{
    background-color: {theme.window};
    color: {theme.text};
}}
QGroupBox, QListWidget, QTableView, QTreeView, QPlainTextEdit, QTextEdit {{
    background-color: {theme.surface};
    border: 1px solid {theme.border};
    border-radius: 4px;
}}
QTableView {{
    gridline-color: {theme.rule};
}}
QGroupBox {{
    /* **Room for the title, which `subcontrol-origin: margin` puts in the margin** (`T-129`).
       Without a margin there is no margin band, so Qt drew the title at y=0 — through the frame's
       own top border and across the first control. Measured before the fix: the title's bottom
       sat 15 px *below* the contents' top, where Qt's own style leaves 5 px of clearance. This is
       the metric the native style supplied and a style sheet has to restore. */
    margin-top: 0.9em;
    padding-top: 6px;
}}
QGroupBox::title {{
    color: {theme.muted};
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    padding: 0 4px;
}}
QHeaderView::section {{
    background-color: {theme.sunken};
    color: {theme.muted};
    border: none;
    border-bottom: 1px solid {theme.rule};
    padding: 4px 6px;
}}
QPushButton {{
    background-color: {theme.surface};
    border: 1px solid {theme.border};
    border-radius: 4px;
    padding: 4px 10px;
}}
QPushButton:default {{
    background-color: {theme.primary};
    border-color: {theme.primary};
    color: {theme.on_primary};
    font-weight: 600;
}}
QPushButton:hover {{
    /* **The states a style sheet takes away** (`T-129`). Styling `QPushButton` at all switches it
       to style-sheet rendering, and Qt then draws hover and pressed exactly like normal unless
       they are declared — so every button on the row looked inert under the pointer. */
    background-color: {theme.sunken};
    border-color: {theme.primary};
}}
QPushButton:pressed {{
    background-color: {theme.rule};
}}
QPushButton:default:hover {{
    /* **The same lift as the toolbar's primary** (`T-147`), and it had the same defect: an
       `accent` ring at 1.42:1 against its own fill. One hover for one kind of button. */
    background-color: {theme.primary_hover};
    border-color: {theme.primary_hover};
}}
QPushButton:disabled {{
    color: {theme.muted};
}}
QMenu {{
    /* **`QWidget` above catches `QMenu`**, which is what dropped the native highlight: a menu is a
       widget, so the universal rule switched it to style-sheet rendering with nothing declared for
       the selected item. Every entry then looked identical to the one under the cursor, on the
       overflow menu `UX-005` §4 makes the keyboard route. */
    background-color: {theme.surface};
    border: 1px solid {theme.border};
    padding: 4px;
}}
QMenu::item {{
    padding: 4px 22px 4px 12px;
    border-radius: 3px;
}}
QMenu::item:selected {{
    background-color: {theme.primary};
    color: {theme.on_primary};
}}
QMenu::item:disabled {{
    color: {theme.muted};
}}
QMenu::separator {{
    height: 1px;
    background: {theme.rule};
    margin: 4px 6px;
}}
QComboBox QAbstractItemView {{
    /* The drop-down list is its own view and does not inherit `QMenu`'s rules. Same defect,
       same remedy: without this, the row's format control highlights nothing as you move. */
    background-color: {theme.surface};
    border: 1px solid {theme.border};
    selection-background-color: {theme.primary};
    selection-color: {theme.on_primary};
}}
QListView, QTreeView, QTableView {{
    /* **A tint, and an inset bar to carry the emphasis** (`T-130`). The full brand fill passed
       contrast and still dominated the list; the mockup's weight is this. `QListView::item` gets
       the left border so the bar sits on the row rather than the viewport. */
    selection-background-color: {theme.selection};
    selection-color: {theme.on_selection};
}}
QListView::item:selected {{
    border-left: 2px solid {theme.primary};
}}
QTabBar::tab:hover {{
    background-color: {theme.sunken};
}}
/* **`QSpinBox` is deliberately absent from the rule above** (`T-133`, corrected).
   Styling the box at all switches it to `QStyleSheetStyle` and its up and down arrows stop being
   drawn — measured at **3 distinct colours in the button strip against 42 native**. The first fix
   declared the sub-controls here and drew the arrows with the CSS border-triangle trick, which
   Qt renders as a **solid block**: measured per-scanline ink widths of `8,8,8,8,8` where a
   triangle gives `2,4,6`. The maintainer saw two dots.
   The alternative was to ship arrow images, which `NFR-004` and `T-033` would then have to carry
   through the frozen artifact for the sake of a triangle. Letting the platform draw its own
   control costs this one widget a themed border and is the smaller commitment by far. */
QToolBar QToolButton {{
    /* **The mockup's `.btn`, and they are buttons** (`T-132`, corrected twice).
       First they stamped a flat `window` fill over the toolbar's own vertical gradient, so the
       tint appeared to stop where the buttons began — measured `#F9FBF9` on the bar against
       `#F5F7F4` inside one. I corrected that by making them **transparent**, which fixed the
       band and destroyed the buttons: `Pause queue` and `Clear finished` became text on a
       toolbar, with no border, no fill and nothing to press.
       The mockup says what they are — `border: 1px solid var(--b); border-radius: 4px;
       background: var(--s)` — and a deliberate shape does not have the first problem, because
       it is not pretending to be the bar. */
    background-color: {theme.surface};
    border: 1px solid {theme.border};
    border-radius: 4px;
    padding: 3px 9px;
}}
QToolBar QToolButton:hover {{
    background-color: {theme.sunken};
    border-color: {theme.primary};
}}
QToolBar QToolButton:pressed {{
    background-color: {theme.rule};
}}
QToolBar QToolButton:disabled {{
    background-color: {theme.window};
    color: {theme.muted};
    border-color: {theme.rule};
}}
QToolBar QToolButton:checked {{
    /* **A paused queue has to look paused** (`T-149`, `NFR-005`). `Pause queue` is one checkable
       action on purpose — pause and resume are the same control — and Qt draws a checked tool
       button sunken until a style sheet replaces its rendering, which the rule above does. So the
       state existed, was announced to a screen reader, and was invisible: pressing the button
       changed nothing anybody could see.
       `T-129` restored hover, pressed and disabled for exactly this reason and missed this one,
       because pause is the only checkable control on the bar and nothing else could have shown it.
       **Not colour alone**: the border thickens as well as darkening, so the state survives a
       greyscale reading. */
    background-color: {theme.rule};
    border: 2px solid {theme.primary};
    padding: 2px 8px;
}}
QToolBar QToolButton:checked:hover {{
    background-color: {theme.sunken};
    border: 2px solid {theme.primary};
    padding: 2px 8px;
}}
QToolBar QWidget[toolbarSpacer="true"] {{
    /* **The spacer is furniture and must not be seen** (`T-132`, corrected). `QWidget` above sets
       a `window` background, and the toolbar's own is `surface` — so the widget that pushes the
       queue verbs to the right end painted a `#F5F7F4` band across a `#FFFFFF` toolbar, measured
       from x=319 to x=715 on a 900px window. A role rather than an object name, for the reason
       `[primaryAction]` above gives. */
    background: transparent;
}}
QWidget[rowPanel="true"] {{
    /* **An opened row is drawn over a row that is still being painted** (`T-210`). `setIndexWidget`
       puts the panel above the item, but the delegate goes on drawing the row underneath — so
       every pixel the panel does not cover showed the row through it: a sliver of thumbnail beside
       the heading, and the row's *Download as* line in the gap above the entries.

       **`setAutoFillBackground` does not do this when a stylesheet is set**, which is the whole
       reason this rule exists rather than a line of Python: a styled widget paints what the sheet
       says and nothing else. Stated here so the panel is opaque by the same mechanism that colours
       it. */
    background: {theme.surface};
}}

QToolButton[disclosure="true"] {{
    /* **The way out of an opened row, drawn as the way in** (`T-210`). The closed row paints a
       disclosure triangle through the style; this is a real `QToolButton` because the panel covers
       that painting and the control has to exist as a widget to be reachable — but it must not
       *look* like a button, or the two halves of one gesture are drawn as two different things.

       A role rather than an object name, for the reason `[primaryAction]` gives: the next panel
       that needs a disclosure inherits this instead of remembering it. */
    border: none;
    background: transparent;
    padding: 0px;
}}
QToolButton[disclosure="true"]:hover {{
    /* Enough to say it is live, without a frame the painted triangle does not have. */
    background: {theme.selection};
    border-radius: 3px;
}}

QStatusBar QLabel[actionableStatus="true"] {{
    /* **The one status-bar line that asks the user to press something** (`T-192`). It sat hard
       against the environment summary at the right end, so *"…press Start to download"* and
       *"ffmpeg found; all post-processing features are available"* ran together as one sentence and
       the request read as the tail of the report. It is on the left now (`addWidget`), and this is
       the second half: weight and colour so it is found rather than parsed.

       `warn` rather than `danger`: a stopped queue is a state the user chose or has not left yet,
       not a failure. `NFR-005` is satisfied before this rule exists — the label says "Queue
       stopped — press Start to download" in words, and this is a second channel on top of them.

       A role rather than an object name, for the reason `[primaryAction]` above gives. The
       property is false while the queue runs, so the running line stays as quiet as the summary
       beside it. */
    color: {theme.warn};
    font-weight: 600;
}}
QComboBox, QLineEdit {{
    background-color: {theme.surface};
    border: 1px solid {theme.border};
    border-radius: 4px;
    padding: 3px 6px;
}}
QComboBox:disabled, QLineEdit:disabled {{
    /* **A control that does nothing must not look like one that does** (`T-139`, and `T-129`'s
       cause for the fourth time). Styling `QComboBox` at all switches it to `QStyleSheetStyle`,
       and the platform's disabled rendering goes with it unless declared — measured, a disabled
       combo drew **pixel-identically** to an enabled one.
       `T-076` has disabled the bitrate for a video preset since it was written, and `UX-005` §5
       forbids a control that accepts a choice nothing acts on. Both were satisfied in behaviour
       and neither was visible: the box still looked settable, so the only way to learn it was
       inert was to try it. */
    background-color: {theme.sunken};
    color: {theme.muted};
    border-color: {theme.rule};
}}
QToolBar QToolButton[primaryAction="true"] {{
    /* **The mockup's `.btn.primary`** (`T-132`, `UX-005`'s second 2026-08-04 amendment). The first
       amendment put the application's primary action first on the toolbar and left it drawn as a
       flat label, indistinguishable from `Clear finished` — where the mockup fills it with the
       brand and the whole point of the row is that one of the four is not like the others.
       Addressed by a **dynamic property** rather than by `QToolBar QToolButton`, which would take
       `Pause queue` and `Clear finished` with it and leave four equals again — and rather than by
       object name, which `test_the_sheet_styles_by_class_so_a_new_widget_inherits_it` forbids for
       a reason this rule would have proved: a second primary action would have had to be
       remembered here, and would silently have been drawn flat. `primaryAction` is a role, so
       anything that declares itself one is themed. */
    background-color: {theme.primary};
    color: {theme.on_primary};
    border: 1px solid {theme.primary};
    border-radius: 4px;
    padding: 4px 12px;
    font-weight: 600;
}}
QToolBar QToolButton[primaryAction="true"]:hover {{
    /* **The fill lifts; there is no ring** (`T-147`). It took an `accent` border, at 1.42:1
       against its own fill in light and 1.25:1 in dark — too low to read as gold and reported as
       a red smudge. See `Theme.primary_hover` for why brightening the accent was not the fix. */
    background-color: {theme.primary_hover};
    border-color: {theme.primary_hover};
}}
QToolBar QToolButton[primaryAction="true"]:pressed {{
    border-color: {theme.accent};
    padding-top: 5px;
    padding-bottom: 3px;
}}
QToolBar QToolButton[primaryAction="true"]:disabled {{
    /* **Part of the ruling, not a detail.** `T-016` disables this when composition supplied no job
       sink or output directory, and a brand fill that stayed vivid while inert would be a worse
       lie than the flat label it replaced: the more emphatic the control, the more it promises. */
    background-color: {theme.sunken};
    color: {theme.muted};
    border-color: {theme.border};
}}
QProgressBar {{
    background-color: {theme.sunken};
    border: 1px solid {theme.border};
    border-radius: 3px;
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {theme.primary};
}}
*:focus {{
    border: 1px solid {theme.accent};
}}
""".strip()


def palette(theme: Theme) -> QPalette:
    """The theme as a `QPalette`, for the widgets that read one directly.

    Set **alongside** the style sheet, not instead of it. Qt has several paths that consult the
    palette rather than the style sheet — item views drawing selections, and anything calling
    `palette().window()` — so a style-sheet-only theme leaves those at the platform default and
    the result reads as two designs at once.

    Imported inside the function so this module can be read, and its arithmetic asserted, without
    Qt. `ui/reveal.py` is the same split for the same reason.
    """
    from PySide6.QtGui import QColor, QPalette

    roles = QPalette()
    roles.setColor(QPalette.ColorRole.Window, QColor(theme.window))
    roles.setColor(QPalette.ColorRole.WindowText, QColor(theme.text))
    roles.setColor(QPalette.ColorRole.Base, QColor(theme.surface))
    roles.setColor(QPalette.ColorRole.AlternateBase, QColor(theme.sunken))
    roles.setColor(QPalette.ColorRole.Text, QColor(theme.text))
    roles.setColor(QPalette.ColorRole.Button, QColor(theme.surface))
    roles.setColor(QPalette.ColorRole.ButtonText, QColor(theme.text))
    # **The brand pair stays here; the row's quiet tint is the style sheet's** (`T130-R1`).
    #
    # This briefly set `Highlight` to `selection`, which is application-wide — and a *row* can
    # afford a subtle tint because it also gets an inset bar, while **selected text in an editor
    # has no second signal**. Measured: a selected URL in the log view came out at 1.14:1 against
    # its own surface, which is invisible rather than quiet. The row tint is scoped to
    # `QListView, QTreeView, QTableView` in the sheet, and Qt propagates that into those widgets'
    # palettes — so `RowDelegate` still reads the tint's pair from `option.palette` (15.55:1) while
    # a text editor keeps the brand highlight (7.64:1).
    roles.setColor(QPalette.ColorRole.Highlight, QColor(theme.primary))
    roles.setColor(QPalette.ColorRole.HighlightedText, QColor(theme.on_primary))
    roles.setColor(QPalette.ColorRole.PlaceholderText, QColor(theme.muted))
    roles.setColor(QPalette.ColorRole.ToolTipBase, QColor(theme.surface))
    roles.setColor(QPalette.ColorRole.ToolTipText, QColor(theme.text))
    # Disabled text is a role of its own: leaving it at the default puts platform grey on a
    # themed ground, which is the one place a half-applied palette is most visible.
    roles.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(theme.muted))
    roles.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(theme.muted))
    roles.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(theme.muted))
    return roles


#: **The theme `apply` last dressed the application in** (`T-165`). A `QPalette` carries the
#: colours Qt has roles for, and the semantic ones — `stop` for a failure, `muted` for something
#: abandoned — have no role to live in. A delegate needing them either hardcodes a hex, which
#: fixes one theme and breaks the other, or asks here.
#:
#: `LIGHT` until `apply` runs, so a widget built in a test without a themed application still
#: gets a coherent set rather than `None`.
_applied: Theme = LIGHT


def applied() -> Theme:
    """The theme in force. See `_applied` for why this exists rather than a wider palette."""
    return _applied


def apply(application: object, theme: Theme = LIGHT) -> None:
    """Dress `application` in `theme`. **The one call that themes anything.**

    Applied to the `QApplication` rather than per widget, which is what makes a widget added
    without asking for a colour inherit the theme rather than becoming the only grey thing on the
    screen.

    `application` is typed loosely so this module needs no Qt import at module scope; anything
    with `setPalette` and `setStyleSheet` satisfies it, which is also how a test drives it without
    a display.
    """
    global _applied
    _applied = theme
    setter = getattr(application, "setPalette", None)
    if setter is not None:
        setter(palette(theme))
    styler = getattr(application, "setStyleSheet", None)
    if styler is not None:
        styler(stylesheet(theme))
