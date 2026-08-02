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
    accent="#8A6412",
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
    accent=GOLD,
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
QGroupBox::title {{
    color: {theme.muted};
    subcontrol-origin: margin;
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
QPushButton:disabled {{
    color: {theme.muted};
}}
QComboBox, QSpinBox, QLineEdit {{
    background-color: {theme.surface};
    border: 1px solid {theme.border};
    border-radius: 4px;
    padding: 3px 6px;
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


def apply(application: object, theme: Theme = LIGHT) -> None:
    """Dress `application` in `theme`. **The one call that themes anything.**

    Applied to the `QApplication` rather than per widget, which is what makes a widget added
    without asking for a colour inherit the theme rather than becoming the only grey thing on the
    screen.

    `application` is typed loosely so this module needs no Qt import at module scope; anything
    with `setPalette` and `setStyleSheet` satisfies it, which is also how a test drives it without
    a display.
    """
    setter = getattr(application, "setPalette", None)
    if setter is not None:
        setter(palette(theme))
    styler = getattr(application, "setStyleSheet", None)
    if styler is not None:
        styler(stylesheet(theme))
