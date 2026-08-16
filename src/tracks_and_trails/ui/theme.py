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


@dataclass(frozen=True, slots=True)
class SemanticRule:
    """One place a semantic colour carries meaning, and the channel that carries it without colour.

    **The pair is the unit** (`T-202`, `NFR-005`: *"no information conveyed by color alone"*). A
    colour and its second channel are one decision, so they are recorded together and asserted
    together — `tests/ui/test_colour_is_never_alone.py` checks that each rule below really is in
    the sheet, with both halves, in both palettes.
    """

    #: The selector, verbatim as `stylesheet` writes it.
    selector: str
    #: `"ok"`, `"warn"` or `"stop"` — the `Theme` field this rule sets.
    colour: str
    #: A declaration in the same rule that says the same thing without colour, verbatim.
    second_channel: str
    #: What the colour means, and where the words that say it live.
    meaning: str


#: Every rule in `stylesheet()` where a semantic colour carries meaning (`T-202`).
#:
#: **The enumeration is the deliverable**, because an unenumerated use is how `NFR-005`'s last
#: clause gets claimed without being met. `T-192` set the shape this follows: the stopped-queue
#: status uses `warn` **and** `font-weight: 600`, applied through a dynamic property so the style
#: is selected by *role* — a new widget in that role inherits both channels rather than having to
#: remember the second.
#:
#: **Adding a semantic colour to `stylesheet()` without adding it here fails a test.** That is the
#: whole mechanism: the sweep matches the palette's semantic values against the generated sheet and
#: requires every occurrence to be claimed, either here or by `COINCIDENTAL_SEMANTIC_VALUES` below.
SEMANTIC_RULES: Final = (
    SemanticRule(
        selector='QStatusBar QLabel[actionableStatus="true"]',
        colour="warn",
        second_channel="font-weight: 600",
        meaning=(
            "The queue is stopped and the user has to press something. The label already says "
            '"Queue stopped — press Start to download" in words; the weight is what makes it '
            "found rather than parsed, and the colour reinforces both."
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class BorderedControl:
    """One control `stylesheet()` gives a border of its own, and whether it can hold the keyboard.

    **The inventory is the deliverable here, not the three rules that came out of it** (`T202-R1`,
    second round). The first correction thickened the border on `QPushButton`, `QComboBox` and
    `QLineEdit` — the three controls the finding named — and left every other bordered control
    recolouring exactly as before. Seven of them, measured at a **literal zero** ink gain.

    A control with a border cannot show focus by *adding* one, so `*:focus` can only change its
    hue. That is a property of having a border, not of being a button, and this is the list of
    everything that has one. `takes_focus` decides which half of the rule applies, and it is
    **checked against Qt** rather than believed: `tests/ui/test_colour_is_never_alone.py` renders
    each control, asks its focus policy, and fails an entry that claims either answer wrongly.
    """

    #: Exactly as `stylesheet()` writes it, so the sweep can match rule for rule.
    selector: str
    #: Whether the keyboard can land here. `False` means the sweep must be able to *prove* it —
    #: Qt reports `NoFocus`, or the control is only ever shown as a popup window.
    takes_focus: bool
    reason: str


#: Every control the sheet gives a `border: <n>px solid` of its own (`T202-R1`).
#:
#: **A bordered control that is not listed here fails a test**, and so does one listed here that
#: the sheet no longer borders. The sweep parses the generated sheet for the border shorthand
#: rather than reading this tuple and believing it, which is the only arrangement where adding a
#: bordered control to the sheet cannot silently skip the focus question.
BORDERED_CONTROLS: Final = (
    BorderedControl(
        selector="QPushButton",
        takes_focus=True,
        reason="A button is a tab stop; this is the control the finding measured 414 pixels on.",
    ),
    BorderedControl(
        selector="QComboBox",
        takes_focus=True,
        reason="A tab stop, and the keyboard opens and changes it — `T-238`'s route depends on it.",
    ),
    BorderedControl(
        selector="QLineEdit",
        takes_focus=True,
        reason="A tab stop, and the one control where the keyboard is the only way to use it.",
    ),
    BorderedControl(
        selector="QListView",
        takes_focus=True,
        reason=(
            "A tab stop with arrow-key navigation inside it. **The base class, not `QListWidget`** "
            "(`T202-R1`, third round): the queue and the add dialog's staging list are plain "
            "`QListView`s, so a rule naming `QListWidget` reached the preset manager and missed "
            "the two lists this application is mostly made of. Left to Qt they were drawn with a "
            "frame at **1.72:1** against the window in light and **1.04:1** in dark — a boundary "
            "under `MINIMUM_CONTROL_CONTRAST` in one palette and invisible in the other, which is "
            "what `Theme.border` exists to prevent."
        ),
    ),
    BorderedControl(
        selector="QTableView",
        takes_focus=True,
        reason="A tab stop — the format table and the queue are both tables and both operable.",
    ),
    BorderedControl(
        selector="QTreeView",
        takes_focus=True,
        reason="A tab stop; the grouped queue is a tree and expands from the keyboard.",
    ),
    BorderedControl(
        selector="QPlainTextEdit",
        takes_focus=True,
        reason="A tab stop, and the log view is read by moving the caret through it.",
    ),
    BorderedControl(
        selector="QTextEdit",
        takes_focus=True,
        reason="A tab stop, for the same reason as the plain edit above.",
    ),
    BorderedControl(
        selector='QToolButton[stepButton="true"]',
        takes_focus=True,
        reason=(
            "`TabFocus`, measured. `T-141`'s own comment says the global ring used to box "
            "whichever stepper had focus, which is a statement that these take it."
        ),
    ),
    BorderedControl(
        selector="QToolBar QToolButton",
        takes_focus=True,
        reason=(
            "`TabFocus` on a `QToolButton` this sheet is handed as a *widget* — which is what "
            "the sweep builds, and why the rule has to exist. **This application's own toolbar "
            "buttons are `NoFocus`**, measured on the composed window: Qt gives an "
            "action-created button `NoFocus`, and `T-234` requires it here — `T203-R3` recorded a "
            "focusable one stealing `Shift+F10` from the row menu. So the rule protects a shape "
            "this application does not currently build, and the entry says which is which rather "
            "than claiming the bar takes focus (`T202-R1`, corrected under `T-246`)."
        ),
    ),
    BorderedControl(
        selector='QToolBar QToolButton[primaryAction="true"]',
        takes_focus=True,
        reason=(
            "The same button with a brand fill, so the same tab stop — and the fill is not a focus "
            "indicator, being there whether or not it holds the keyboard."
        ),
    ),
    BorderedControl(
        selector="QGroupBox",
        takes_focus=False,
        reason=(
            "`NoFocus`. A group box is a frame with a caption: it has no value, no action and no "
            "tab stop, and Qt gives the keyboard to the controls inside it instead."
        ),
    ),
    BorderedControl(
        selector="QProgressBar",
        takes_focus=False,
        reason="`NoFocus`. It reports; there is nothing to operate and nowhere for focus to land.",
    ),
    BorderedControl(
        selector="QMenu",
        takes_focus=False,
        reason=(
            "`NoFocus`, and a popup window besides. A menu is only ever on screen while it is the "
            "thing being used, so there is no unfocused state for a ring to distinguish it from."
        ),
    ),
    BorderedControl(
        selector="QComboBox QAbstractItemView",
        takes_focus=False,
        reason=(
            "A popup window. The view itself reports `StrongFocus`, and it is exempt on the menu's "
            "grounds rather than on that one: it exists only while the drop-down is open, so a "
            "ring saying *this has the keyboard* would be drawn on every popup that ever appears."
        ),
    ),
)

#: The one selector whose border goes from 1px to 2px when the control takes the keyboard.
#:
#: **Built from `BORDERED_CONTROLS` rather than typed out**, so the rule in `stylesheet()` and the
#: inventory above cannot disagree. Retyping the list was how the first correction covered three
#: controls and left seven behind; a list that exists once cannot be extended in one place only.
THICKENED_FOCUS_SELECTOR: Final = ", ".join(
    f"{control.selector}:focus" for control in BORDERED_CONTROLS if control.takes_focus
)


#: Occurrences of a semantic colour's **value** in the sheet that are not semantic uses.
#:
#: **`warn` and `accent` are the same hex in the dark palette** — both `GOLD`, `#D9A24C` — so a
#: sweep matching by value finds the focus ring and the pressed primary action there and finds
#: neither in light. That is a property of the palette, not of the rules: nothing about a focus
#: ring means *warning*, and the two would have to be told apart by hand in exactly one theme.
#:
#: Listed by selector rather than excused by a colour comparison, so a rule that starts meaning
#: something has to be moved out of this tuple deliberately.
COINCIDENTAL_SEMANTIC_VALUES: Final = (
    "*:focus",
    "QScrollArea:focus",
    THICKENED_FOCUS_SELECTOR,
    'QToolBar QToolButton[primaryAction="true"]:focus',
    'QToolBar QToolButton[primaryAction="true"]:pressed',
)


@dataclass(frozen=True, slots=True)
class StateRule:
    """One interaction state a rule draws, and the channel that carries it besides colour.

    **Enumerated by the information conveyed, not by the palette field used** (`T202-R1`).
    `SEMANTIC_RULES` below asks *which rules use `ok`, `warn` or `stop`*, and that question missed
    the defect entirely: the focus ring is drawn in `accent`, which is not a semantic field, and
    focus is unmistakably information. A control's *state* is information whatever colour draws it.
    """

    selector: str
    #: What this rule tells the user.
    conveys: str
    #: How it says it without colour — see `StateChannel` for the four kinds and why each counts.
    channel: str
    reason: str


#: The channels a state may use instead of colour, and what makes each acceptable.
#:
#: - `geometry` — ink appears where there was none, or an edge changes thickness or shape. Survives
#:   greyscale, a monochrome display, and any colour vision. The strongest of the four.
#: - `luminance` — the fill inverts far enough that the change reads as brightness rather than hue.
#:   Asserted against `MINIMUM_CONTRAST` rather than asserted by eye.
#: - `published-state` — the state is in the accessibility tree, so a screen reader announces it
#:   whether or not anything is drawn. `:disabled` is the case, and `QAccessible` is asked directly.
#: - `pointer-feedback` — **not state.** Hover and pressed describe where the pointer is, to the
#:   person holding it; they tell a keyboard or screen-reader user nothing, because that user is
#:   not hovering. A rule in this class conveys no information to lose.
STATE_CHANNELS: Final = frozenset({"geometry", "luminance", "published-state", "pointer-feedback"})

#: Every rule in `stylesheet()` that draws an interaction state (`T202-R1`).
#:
#: **A pseudo-state selector that is not listed here fails a test.** That is the completeness half:
#: the previous sweep enumerated only rules using a semantic colour field, so a state drawn in
#: `accent` — focus, exactly — was never asked what it meant.
STATE_RULES: Final = (
    StateRule(
        selector="*:focus",
        conveys="keyboard focus, on a control with no border of its own",
        channel="geometry",
        reason=(
            "A ring appears where there was nothing. For a check box, a radio button or a "
            "borderless control this is ink against background, which needs no colour to read."
        ),
    ),
    StateRule(
        selector=THICKENED_FOCUS_SELECTOR,
        conveys="keyboard focus, on every control that already has a border",
        channel="geometry",
        reason=(
            "The border goes from 1px to 2px. Recolouring it was the defect: measured on a "
            "rendered button, 414 pixels changed and none of them was background becoming ink, "
            "with the two hues 1.45:1 apart in light and 2.17:1 in dark. The list is "
            "`BORDERED_CONTROLS`, not the three controls the finding named."
        ),
    ),
    StateRule(
        selector="QPushButton:focus",
        conveys="keyboard focus — the padding half of the rule above",
        channel="geometry",
        reason="Padding drops by exactly what the border gains, so the control does not move.",
    ),
    StateRule(
        selector="QComboBox:focus, QLineEdit:focus",
        conveys="keyboard focus — the padding half of the rule above",
        channel="geometry",
        reason="Padding drops by exactly what the border gains, so the control does not move.",
    ),
    StateRule(
        selector=(
            "QListView:focus, QTableView:focus, QTreeView:focus, QPlainTextEdit:focus, "
            "QTextEdit:focus"
        ),
        conveys="keyboard focus — the padding half, for the views and the text edits",
        channel="geometry",
        reason=(
            "These had no padding to give up, so the idle rule grants them one pixel and this "
            "spends it; without it the thicker border is drawn over the first row rather than "
            "beside it, because Qt does not re-measure a frame when focus arrives."
        ),
    ),
    StateRule(
        selector='QToolButton[stepButton="true"]:focus',
        conveys="keyboard focus — the padding half, for a stepper",
        channel="geometry",
        reason=(
            "Vertical only: `min-width` and `max-width` pin the contents box, so the sides cannot "
            "move whatever the border does, and the top and bottom each give up their pixel."
        ),
    ),
    StateRule(
        selector="QToolBar QToolButton:focus",
        conveys="keyboard focus — the padding half, for a toolbar verb",
        channel="geometry",
        reason=(
            "Tab reaches these, measured, and the figures land on `T-149`'s checked geometry "
            "exactly — so a focused, paused button keeps its shape and takes the accent hue."
        ),
    ),
    StateRule(
        selector="QScrollArea:focus",
        conveys="keyboard focus, on a container Qt puts in the tab chain",
        channel="geometry",
        reason=(
            "A two-pixel ring appears where a `NoFrame` container had no edge at all, paid for by "
            "the padding above so nothing moves. One pixel was measured as good as nothing: 254 "
            "changed pixels against a floor of 1516 on the Settings screen's scroller."
        ),
    ),
    StateRule(
        selector='QPushButton:default:focus, QToolBar QToolButton[primaryAction="true"]:focus',
        conveys="keyboard focus, on the two controls whose ground is the brand fill",
        channel="geometry",
        reason=(
            "The ring is drawn in `on_primary` rather than `accent`, because accent on that fill "
            "is 1.42:1 in light and 1.25:1 in dark — `T-147`'s own measurement — so thickening it "
            "left an edge a greyscale reader still could not see. Measured at zero changed pixels "
            "before this rule and a full ring after."
        ),
    ),
    StateRule(
        selector="QComboBox QAbstractItemView, QComboBox QAbstractItemView:focus",
        conveys="nothing — a drop-down is never on screen without the keyboard",
        channel="geometry",
        reason=(
            "The one bordered control that keeps its 1px edge when focused, because it has no "
            "unfocused state to be told apart from; listed here so the exemption is enumerated "
            "rather than implied, and proved by asking Qt whether it is a popup window."
        ),
    ),
    StateRule(
        selector='QToolBar QToolButton[primaryAction="true"]:focus',
        conveys="keyboard focus — the padding half, for the primary verb",
        channel="geometry",
        reason=(
            "Its idle padding is wider than the plain verb's, so it needs its own figure; the "
            "brand fill is not a focus indicator, being there whether or not it has the keyboard."
        ),
    ),
    StateRule(
        selector="QToolBar QToolButton:checked",
        conveys="the queue is paused",
        channel="geometry",
        reason=(
            "`T-149`'s rule, and the precedent the focus fix follows: the border thickens to 2px "
            "against a reduced padding, so the state survives a greyscale reading."
        ),
    ),
    StateRule(
        selector="QToolBar QToolButton:checked:hover",
        conveys="the queue is paused, with the pointer over the control",
        channel="geometry",
        reason="Carries the checked rule's 2px border unchanged; only the fill differs.",
    ),
    StateRule(
        selector="QListView::item:selected",
        conveys="which row is selected",
        channel="geometry",
        reason="A 2px bar appears down the left edge — `T-130`'s inset, and a shape, not a tint.",
    ),
    StateRule(
        selector="QMenu::item:selected",
        conveys="which menu item the keyboard or pointer is on",
        channel="luminance",
        reason=(
            "The fill inverts to the brand green with its own foreground, a change in brightness "
            "rather than hue; the pair is asserted against MINIMUM_CONTRAST rather than trusted."
        ),
    ),
    StateRule(
        selector="QPushButton:disabled",
        conveys="this control cannot be used",
        channel="published-state",
        reason=(
            "Qt publishes `state().disabled`, which a screen reader announces whether or not "
            "anything is drawn; asserted directly in tests/ui/test_colour_is_never_alone.py."
        ),
    ),
    StateRule(
        selector="QMenu::item:disabled",
        conveys="this menu item cannot be used",
        channel="published-state",
        reason=(
            "Qt publishes the disabled state, and the item is unselectable as well, so the "
            "keyboard skips over it rather than landing somewhere that does nothing."
        ),
    ),
    StateRule(
        selector="QComboBox:disabled, QLineEdit:disabled",
        conveys="this control cannot be used",
        channel="published-state",
        reason=(
            "Qt publishes the disabled state, and `T-139` records why the rule exists at all: a "
            "styled combo drew pixel-identically to an enabled one until it was declared."
        ),
    ),
    StateRule(
        selector='QToolButton[stepButton="true"]:disabled',
        conveys="this stepper cannot be used",
        channel="published-state",
        reason=(
            "Qt publishes the disabled state, and the spin box these steppers drive publishes its "
            "own, so the keyboard route named by `route_is_elsewhere` reports it too."
        ),
    ),
    StateRule(
        selector="QToolBar QToolButton:disabled",
        conveys="this toolbar verb cannot be used",
        channel="published-state",
        reason=(
            "Qt publishes the disabled state on the action behind the button, so a screen reader "
            "announces it even though nothing on this bar takes focus — `T-234`'s criterion, "
            "measured `NoFocus` on all four of the composed window's toolbar buttons."
        ),
    ),
    StateRule(
        selector='QToolBar QToolButton[primaryAction="true"]:disabled',
        conveys="the primary verb cannot be used",
        channel="published-state",
        reason="As above, and `T-016`'s reason for dropping the brand fill when it is inert.",
    ),
    StateRule(
        selector="QPushButton:default",
        conveys="which button Return will press",
        channel="geometry",
        reason=(
            "The brand fill arrives with `font-weight: 600`, so the default reads as heavier text "
            "as well as a different ground; the weight is what survives a greyscale reading."
        ),
    ),
    StateRule(
        selector="QPushButton:hover",
        conveys="nothing — the pointer is over this control",
        channel="pointer-feedback",
        reason="Only a pointer user can be hovering, and they can see where their pointer is.",
    ),
    StateRule(
        selector="QPushButton:default:hover",
        conveys="nothing — the pointer is over the default button",
        channel="pointer-feedback",
        reason=(
            "Only a pointer user can hover, and the default button already says it is the default "
            "by its weight rather than by this rule."
        ),
    ),
    StateRule(
        selector="QPushButton:pressed",
        conveys="nothing — this control is being pressed right now",
        channel="pointer-feedback",
        reason="Transient, and the press is the user's own action.",
    ),
    StateRule(
        selector="QTabBar::tab:hover",
        conveys="nothing — the pointer is over a tab",
        channel="pointer-feedback",
        reason=(
            "Only a pointer user can hover; which tab is current is a different state, drawn by "
            "the tab bar itself rather than by this rule."
        ),
    ),
    StateRule(
        selector='QToolButton[stepButton="true"]:hover',
        conveys="nothing — the pointer is over a stepper",
        channel="pointer-feedback",
        reason=(
            "Only a pointer user can hover, and `T-141` gave these a border of their own so they "
            "look like controls without needing this rule."
        ),
    ),
    StateRule(
        selector='QToolButton[stepButton="true"]:pressed',
        conveys="nothing — a stepper is being pressed",
        channel="pointer-feedback",
        reason=(
            "Transient feedback for the duration of a press the user is themselves making, and "
            "the value it changes is announced by the spin box."
        ),
    ),
    StateRule(
        selector='QToolButton[disclosure="true"]:hover',
        conveys="nothing — the pointer is over a disclosure control",
        channel="pointer-feedback",
        reason=(
            "Only a pointer user can hover; whether the row is expanded is published separately "
            "and drawn by the twisty rather than by this rule."
        ),
    ),
    StateRule(
        selector="QToolBar QToolButton:hover",
        conveys="nothing — the pointer is over a toolbar verb",
        channel="pointer-feedback",
        reason=(
            "Only a pointer user can hover, and `T-129` restored these purely so the bar stops "
            "looking inert under a pointer."
        ),
    ),
    StateRule(
        selector="QToolBar QToolButton:pressed",
        conveys="nothing — a toolbar verb is being pressed",
        channel="pointer-feedback",
        reason=(
            "Transient feedback for the duration of a press, and the result of the press is "
            "announced by whatever it changes."
        ),
    ),
    StateRule(
        selector='QToolBar QToolButton[primaryAction="true"]:hover',
        conveys="nothing — the pointer is over the primary verb",
        channel="pointer-feedback",
        reason=(
            "Only a pointer user can hover; `T-147` made this a lighter fill rather than a ring "
            "precisely so it reads as feedback and not as a state."
        ),
    ),
    StateRule(
        selector='QToolBar QToolButton[primaryAction="true"]:pressed',
        conveys="nothing — the primary verb is being pressed",
        channel="pointer-feedback",
        reason=(
            "Transient, and `T-147` gives it a one-pixel inset rather than a colour change in any "
            "case, so it is geometry even though it need not be."
        ),
    ),
)


#: Rules where `muted` is **secondary emphasis** — quieter, not unavailable.
#:
#: `T-202` asks for grey to be covered or for the sweep to record that it never carries state.
#: Measured 2026-08-15: it does both, and the two are told apart by the selector. Every other
#: `muted` rule in the sheet is a `:disabled` one, where the state is published to the
#: accessibility tree as well as drawn — `QAccessible` reports `state().disabled`, asserted rather
#: than assumed — and where the control also does not respond. Grey is the third channel there,
#: not the only one.
SECONDARY_EMPHASIS_SELECTORS: Final = (
    "QGroupBox::title",
    "QHeaderView::section",
)


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
QGroupBox, QListView, QTableView, QTreeView, QPlainTextEdit, QTextEdit {{
    background-color: {theme.surface};
    border: 1px solid {theme.border};
    border-radius: 4px;
}}
QListView, QTableView, QTreeView, QPlainTextEdit, QTextEdit {{
    /* **A pixel of padding, so focus has something to spend** (`T202-R1`, second round). Every
       control whose border thickens on focus pays for the extra pixel out of its own padding, and
       these had none. **Qt does not re-measure a frame when focus arrives** — the width is taken
       from the sheet at polish time — so without this the thicker border is not pushed outward and
       the contents are not pushed in: the extra pixel is drawn *on top of* the first row of the
       list and the first line of the log. Measured with this rule deleted: the viewport keeps its
       geometry to the pixel, `frameWidth()` still reports 1, and **754 pixels of the contents'
       own edge are repainted**. Held to that by
       `test_focus_does_not_paint_over_the_contents`, which is a different assertion from *nothing
       moves* and had to be, because nothing does.

       **`QGroupBox` is deliberately not in this list**, though it shares the rule above. It has
       `NoFocus` — asserted, not assumed, in `test_a_bordered_control_left_out_of_the_inventory`
       — so it never thickens and has nothing to pay for, and its own `padding-top` is `T-129`'s
       measured clearance for the title. Widening this selector by one class would have moved every
       group's contents to buy a pixel nothing would ever use. */
    padding: 1px;
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
QComboBox QAbstractItemView, QComboBox QAbstractItemView:focus {{
    /* The drop-down list is its own view and does not inherit `QMenu`'s rules. Same defect,
       same remedy: without this, the row's format control highlights nothing as you move.

       **Both states, because the rule above now borders every `QListView` and this is one**
       (`T202-R1`, third round). A popup is on screen only while it is the thing being used, so it
       is never *not* focused: a ring that appeared on focus would distinguish it from a state it
       is never in, and the 1px of padding that pays for one would inset the list for nothing.
       `BORDERED_CONTROLS` records the same exemption, and the sweep proves it by asking Qt
       whether this is a popup window rather than by taking the reason on trust. */
    background-color: {theme.surface};
    border: 1px solid {theme.border};
    padding: 0px;
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
QToolButton[stepButton="true"] {{
    /* **A pair has to look like a pair** (`T-141`, corrected; rebuilt by `T-236`). Left bare,
       these were transparent text — and the global `*:focus` rule then drew an accent border on
       whichever one had focus, so the minus appeared boxed and the plus did not. Two controls
       doing the same kind of thing in opposite directions must not differ in whether they look
       like controls at all.
       Given a border of their own, focus deepens an edge that is already there instead of
       inventing one on one of them.
       **Not scoped to `QToolBar` any more** (`T-236`). It was, because the control was on one;
       `UX-013` moved it into the Settings screen, and a selector that still said `QToolBar` would
       match nothing and fail exactly the way this comment's first paragraph describes — silently,
       with the buttons back to looking like text. Scoped by the role property alone, which is
       what `theme.py` styles by. */
    background-color: {theme.surface};
    border: 1px solid {theme.border};
    border-radius: 4px;
    min-width: 15px;
    max-width: 15px;
    padding: 1px 0 2px 0;
    font-weight: 600;
}}
QToolButton[stepButton="true"]:hover {{
    background-color: {theme.sunken};
    border-color: {theme.primary};
}}
QToolButton[stepButton="true"]:pressed {{
    background-color: {theme.rule};
}}
QToolButton[stepButton="true"]:disabled {{
    /* At the range's end. Quieter, still a shape — a control that vanished at the limit would
       read as the application breaking rather than the limit being reached. */
    background-color: {theme.window};
    color: {theme.muted};
    border-color: {theme.rule};
}}
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
QScrollArea {{
    /* **Two pixels of padding, for the ring below to spend** (`T202-R1`, third round). A scroll
       area is a `NoFrame` container with nothing to thicken, and `Qt` makes it a tab stop: the
       keyboard lands on the Settings screen's scroller and on the options dialog's, and until this
       rule the global one-pixel ring drew so little of itself that the whole-application sweep
       measured **254 changed pixels against a 1516 floor** on the first and a marginal **1146
       against 1175** on the second. A container is a strange thing to give the keyboard, and that
       is Qt's default rather than this application's decision — but while it is a tab stop it has
       to say so. */
    padding: 2px;
}}
QScrollArea:focus {{
    /* Two pixels, because one measured as good as nothing here, and the padding above pays for
       both so the contents do not move: measured, the viewport keeps `QRect(2, 2, 550, 693)`
       exactly. */
    border: 2px solid {theme.accent};
    padding: 0px;
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
    /* **For a widget with no border of its own, this ring *is* the non-colour channel**
       (`T202-R1`): focus makes ink appear where there was background, which survives a greyscale
       reading and a monochrome display alike. A check box, a radio button and a label-like control
       are all in this case.

       For a control that already has a one-pixel border it is **not** enough, and the rules below
       are why. */
    border: 1px solid {theme.accent};
}}
{THICKENED_FOCUS_SELECTOR} {{
    /* **Focus thickens the edge; it does not merely recolour it** (`T202-R1`, `NFR-005`).

       Every control listed here already carries a one-pixel border, so the global rule above
       changed nothing but the hue. Measured on a rendered `QPushButton`: **414 pixels changed,
       and not one of them was background becoming ink** — the geometry was identical and the two
       border colours sit **1.45:1** apart in light and **2.17:1** in dark. A user who cannot
       separate those hues had no focus indicator at all, which is the keyboard user this whole
       task exists to protect.

       **The list is every bordered control that can hold the keyboard, and the first round had
       three of them.** The other seven scored a **literal zero** on the same rendered measurement
       — a list, a table, a tree, two text edits, a stepper and a toolbar verb, in both palettes —
       because the fix was written against the three controls the finding happened to name rather
       than against the property they shared. `BORDERED_CONTROLS` is the enumeration now, and a
       bordered focusable control missing from it fails a test rather than waiting for a reviewer.

       **The padding is reduced by exactly what the border gains**, so nothing moves; the rules
       below are that half, one per idle padding. That is not a new trick here: `QToolBar
       QToolButton:checked` has thickened to 2px against `padding: 2px 8px` since `T-149`, for the
       same reason and with the same arithmetic — and because that rule comes first, a focused
       *and* checked `Pause queue` keeps the checked geometry exactly and takes the accent hue,
       with `background-color: {theme.rule}` still saying which state it is in. */
    border: 2px solid {theme.accent};
}}
QPushButton:focus {{
    padding: 3px 9px;
}}
QComboBox:focus, QLineEdit:focus {{
    padding: 2px 5px;
}}
QListView:focus, QTableView:focus, QTreeView:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    padding: 0px;
}}
QToolButton[stepButton="true"]:focus {{
    /* Vertical only: `min-width` and `max-width` pin the *contents* box at 15px, so the sides are
       already at zero and the width cannot move whatever the border does. */
    padding: 0 0 1px 0;
}}
QToolBar QToolButton:focus {{
    padding: 2px 8px;
}}
QToolBar QToolButton[primaryAction="true"]:focus {{
    /* **The brand fill is not a focus indicator** — it is there whether or not the button holds
       the keyboard, and `T-147` deliberately left it without a ring on hover. The border above
       thickens it like any other bordered control; only the padding differs, because its idle
       padding is wider than the plain verb's. The attribute selector outranks `QToolBar
       QToolButton:focus`, which would otherwise apply the narrower figure and move the button. */
    padding: 3px 11px;
}}
QPushButton:default:focus, QToolBar QToolButton[primaryAction="true"]:focus {{
    /* **A ring is only a ring if it contrasts with the fill it is drawn on** (`T202-R1`, third
       round). These two are the controls whose ground is `primary`, and `T-147` measured accent
       against that ground at **1.42:1 in light and 1.25:1 in dark** — its exact words, about the
       hover ring it removed for this reason. The focus rule then put the same unreadable pair
       back: thickening a border a greyscale reader cannot see leaves it a border they cannot see,
       and the whole-application sweep measured **zero** changed pixels on both.

       `on_primary` is the one colour guaranteed to work here, because it is what this fill was
       chosen to carry text in — **7.64:1** in light and **5.00:1** in dark, against the 3:1 that
       `MINIMUM_CONTROL_CONTRAST` asks of an edge.

       **Qt hands `:default` to whichever button has focus**, which is why this is not only about
       the button that starts out default: in a dialog, every button's ground turns `primary` at
       the moment it takes the keyboard. For the others the fill inverting is itself the change a
       greyscale reader sees; for the one already wearing it, this ring is all there is. */
    border-color: {theme.on_primary};
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
