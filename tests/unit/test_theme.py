"""The brand palette (`T-120`, `ARCHITECTURE.md` §8, `NFR-005`).

No `QApplication`: `ui/theme.py` keeps its arithmetic Qt-free precisely so legibility can be
asserted as arithmetic rather than inspected as a screenshot. The two functions that do touch Qt
are driven through a recorder, which is enough — what they set is a value, and a real
`QApplication` would prove nothing extra about it.
"""

from typing import Any

import pytest

from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.ui import theme
from tracks_and_trails.ui.job_detail import STATUS_TEXT
from tracks_and_trails.ui.theme import (
    DARK,
    DEEP,
    FOREST,
    GOLD,
    LIGHT,
    MINIMUM_CONTRAST,
    MINIMUM_CONTROL_CONTRAST,
    THEMES,
    Theme,
    contrast_ratio,
    relative_luminance,
    stylesheet,
)

#: Every pair a user reads text from. **Written out rather than derived from the dataclass**: a
#: field added without deciding what it sits on would be swept into a derived list and pass by
#: default, which is the opposite of noticing it (`ai/TESTING.md` §13).
TEXT_PAIRS = (
    ("text", "window"),
    ("text", "surface"),
    ("text", "sunken"),
    ("muted", "window"),
    ("muted", "surface"),
    ("muted", "sunken"),
    ("on_primary", "primary"),
    ("accent", "surface"),
    ("ok", "surface"),
    ("warn", "surface"),
    ("stop", "surface"),
)

#: Edges of things you can operate. A divider is deliberately absent — see
#: `MINIMUM_CONTROL_CONTRAST` for why a hairline has no floor.
CONTROL_PAIRS = (
    ("border", "surface"),
    ("border", "window"),
)


class RecordingApplication:
    """Stands in for a `QApplication`. What `apply` sets is a value, not a rendering."""

    def __init__(self) -> None:
        self.palette: Any = None
        self.sheet: str | None = None

    def setPalette(self, palette: Any) -> None:  # noqa: N802 - Qt's name
        self.palette = palette

    def setStyleSheet(self, sheet: str) -> None:  # noqa: N802 - Qt's name
        self.sheet = sheet


# --- the arithmetic ---------------------------------------------------------------------------


def test_relative_luminance_anchors_at_black_and_white() -> None:
    """The two values WCAG fixes, so a sign error or a missing gamma step cannot pass."""
    assert relative_luminance("#000000") == pytest.approx(0.0)
    assert relative_luminance("#FFFFFF") == pytest.approx(1.0)


def test_contrast_is_symmetric_and_bounded() -> None:
    """21:1 is the maximum the standard defines, and the ratio does not care about argument order.

    Symmetry matters here: without it a test could pass by putting the colours the other way
    round, which is the kind of accident that makes a failing palette look fine.
    """
    assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert contrast_ratio("#FFFFFF", "#000000") == pytest.approx(21.0)
    assert contrast_ratio("#123456", "#123456") == pytest.approx(1.0)
    assert contrast_ratio(FOREST, "#FFFFFF") == pytest.approx(contrast_ratio("#FFFFFF", FOREST))


@pytest.mark.parametrize(
    "bad", ["", "#FFF", "1E5E47", "###1E5E47", "#GGGGGG", "#1E5E4", "#1E5E477"]
)
def test_a_colour_that_is_not_rrggbb_is_refused(bad: str) -> None:
    """Guessing at a malformed colour is how a theme half-applies and nobody notices."""
    with pytest.raises(ValueError):
        relative_luminance(bad)


# --- legibility, in both themes -----------------------------------------------------------------


@pytest.mark.parametrize("theme_name", sorted(THEMES))
@pytest.mark.parametrize(("foreground", "background"), TEXT_PAIRS)
def test_every_text_pair_meets_the_contrast_floor(
    theme_name: str, foreground: str, background: str
) -> None:
    """`NFR-005` needs a threshold something can fail, and this is it.

    Both themes, every pair, rather than a spot check on the one that looked worst. Two real
    failures came out of writing this: the dark primary measured **4.33** with `DEEP` on it —
    near enough to pass by eye — and one colour was doing duty as both a divider and a control
    edge, failing the control floor in both themes.
    """
    palette = THEMES[theme_name]
    ratio = contrast_ratio(getattr(palette, foreground), getattr(palette, background))
    assert ratio >= MINIMUM_CONTRAST, (
        f"{theme_name}: {foreground} on {background} is {ratio:.2f}:1, below {MINIMUM_CONTRAST}:1"
    )


@pytest.mark.parametrize("theme_name", sorted(THEMES))
@pytest.mark.parametrize(("foreground", "background"), CONTROL_PAIRS)
def test_every_control_edge_meets_the_non_text_floor(
    theme_name: str, foreground: str, background: str
) -> None:
    """A control whose boundary is invisible is a control you cannot find."""
    palette = THEMES[theme_name]
    ratio = contrast_ratio(getattr(palette, foreground), getattr(palette, background))
    assert ratio >= MINIMUM_CONTROL_CONTRAST, (
        f"{theme_name}: {foreground} on {background} is {ratio:.2f}:1, below "
        f"{MINIMUM_CONTROL_CONTRAST}:1"
    )


def test_the_dark_theme_is_not_an_inversion_of_the_light_one() -> None:
    """Each theme names its own values, and the accent is the one that gives an inversion away.

    A flipped light theme keeps the same accent on a dark ground, where it is either muddy or
    glaring. Asserted on the values rather than on a promise in a docstring.
    """
    assert LIGHT.accent != DARK.accent, "both themes use one accent, so one of them is wrong"


def test_every_queue_state_is_named_in_words() -> None:
    """`NFR-005`: colour may reinforce a state, but never replace its textual name."""
    assert set(STATUS_TEXT) == set(JobStatus)
    assert all(text.strip() for text in STATUS_TEXT.values())
    assert LIGHT.primary != DARK.primary
    for field in ("window", "surface", "sunken", "text", "muted", "rule", "border"):
        assert getattr(LIGHT, field) != getattr(DARK, field), f"{field} is shared between themes"


def test_both_themes_quote_the_canonical_swatches() -> None:
    """`ARCHITECTURE.md` §8's three hexes are the definition, and appear as themselves somewhere.

    Not "every role is one of the three" — a palette needs grounds and greys the brand does not
    name. What this refuses is a theme that quietly stops using the brand at all.
    """
    assert FOREST == "#1E5E47"
    assert GOLD == "#D9A24C"
    assert DEEP == "#083122"
    assert LIGHT.primary == FOREST, "the light theme stopped using the brand primary"
    assert DARK.accent == GOLD, "the dark theme stopped using the brand accent"
    assert DARK.on_primary == DEEP


# --- applying it ---------------------------------------------------------------------------------


def test_applying_the_theme_sets_both_the_palette_and_the_sheet() -> None:
    """`QPalette` cannot express a border and a style sheet does not reach every Qt path.

    Setting only one leaves half the surface at the platform default, which reads as two designs
    at once — so this asserts both, rather than that "theming happened".
    """
    application = RecordingApplication()

    theme.apply(application, DARK)

    assert application.palette is not None, "no palette was set"
    assert application.sheet is not None and application.sheet.strip(), "no style sheet was set"
    assert DARK.surface in application.sheet


def test_the_sheet_styles_by_class_so_a_new_widget_inherits_it() -> None:
    """Naming widgets individually is how a new panel becomes the only grey thing on the screen.

    Asserted by looking for the object-name selector Qt uses (`#objectName`), because that is the
    thing whose absence is the property: a sheet full of them is a sheet that themes exactly the
    widgets someone remembered.
    """
    sheet = stylesheet(LIGHT)

    assert "#" in sheet, "no colours at all, so this is asserting nothing"
    selectors = [line for line in sheet.splitlines() if line.rstrip().endswith("{")]
    named = [line for line in selectors if "#" in line]
    assert not named, f"the sheet styles widgets by name rather than by class: {named}"
    assert "QWidget {" in sheet, "nothing sets a default, so an unstyled widget stays unstyled"


@pytest.mark.parametrize("theme_name", sorted(THEMES))
def test_every_role_reaches_the_sheet(theme_name: str) -> None:
    """A role defined and never used is a colour that does nothing, which is worth knowing.

    `rule` is the exception this names rather than hides: it is the table gridline, and it reaches
    the sheet through `gridline-color`.
    """
    palette: Theme = THEMES[theme_name]
    sheet = stylesheet(palette)
    for field in ("window", "surface", "sunken", "text", "muted", "rule", "border", "primary"):
        assert getattr(palette, field) in sheet, f"{field} is defined and never drawn"


def test_applying_to_something_without_qts_setters_does_not_raise() -> None:
    """`apply` is called once, at startup, before anything else can report a problem.

    A `TypeError` there is a window that never opens and a traceback nobody reads, so the setters
    are asked for rather than assumed.
    """
    theme.apply(object(), LIGHT)
