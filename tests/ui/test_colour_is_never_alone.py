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
from collections.abc import Iterator
from typing import Final

import pytest
from PySide6.QtGui import QAccessible
from PySide6.QtWidgets import QApplication, QComboBox, QPushButton

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
    """
    for selector, body in _RULE.findall(ui_theme.stylesheet(theme)):
        yield " ".join(selector.split()), _COMMENT.sub("", body)


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
