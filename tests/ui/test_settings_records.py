"""The records that say which `REQ-023` settings are built (`T-227`).

**What this gate covers, stated where it is defined**, because a gate whose reach is unclear is a
claim that the documents are checked:

| Surface | Covered | How |
|---|---|---|
| The screen's *still to come* sentence | **Yes, structurally** | Derived from `REQ_023_SETTINGS` |
| Each setting's control | **Yes** | The screen is built and each declared control looked up |
| `docs/DEVELOPMENT.md` §coverage | **Yes** | `req023:<key> built|unbuilt` markers, per row |
| `docs/UX_SPEC.md` §2's count | **Yes** | One `req023:count built=N total=N` marker |
| Every other sentence in those files | **No** | Free prose, deliberately — see below |
| Docstrings that state the count | **No** | See below |

**The markers are read and the prose is not, and that is the design rather than a shortcut.**
`T214-R1` and `T214-R2` are one lesson twice: *a guard proved against one spelling is a guard
against one spelling*. A test grepping for the word *five* passes the moment somebody writes *5*,
or *all but three*, or moves the count into a table — and **a gate that can be defeated by
rephrasing is worse than no gate**, because it is also a claim that the documents are checked. An
HTML comment is invisible to every renderer, survives any rewording around it, and cannot be
satisfied by accident.

**What is deliberately not covered, and what that costs.** `ui/settings_dialog.py`'s module
docstring and `core/settings.Settings`' docstring both state the count in prose, and both have
rotted before (`T-195`'s sixth criterion). They are not gated here: a marker inside a docstring
would be read by a person as noise in the one place the reasoning lives, and unlike a document
those two sit **in the diff of any change to the thing they describe**. The residual is real —
a reviewer is what catches them — and it is smaller than it was, because the count is no longer
something anybody has to remember: `REQ_023_SETTINGS` is.

**The mutation this exists to fail is not "change the number".** It is *build a setting and update
nothing*, which is the sequence that produced `T-227`. `test_a_setting_built_without_touching_the
_documents_is_caught` performs exactly that and asserts the gate goes red.
"""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from tracks_and_trails.ui.settings_dialog import (
    REQ_023_SETTINGS,
    SETTINGS_STILL_TO_COME,
    Req023Setting,
    SettingsDialog,
    still_to_come,
)

REPOSITORY: Final = Path(__file__).resolve().parents[2]
DEVELOPMENT: Final = REPOSITORY / "docs" / "DEVELOPMENT.md"
UX_SPEC: Final = REPOSITORY / "docs" / "UX_SPEC.md"

#: One row of the coverage table: its key, and whether that row says the setting is built.
_ROW: Final = re.compile(r"<!--\s*req023:(?P<key>[a-z0-9-]+)\s+(?P<state>built|unbuilt)\s*-->")

#: `docs/UX_SPEC.md` §2's count marker.
_COUNT: Final = re.compile(
    r"<!--\s*req023:count\s+built=(?P<built>\d+)\s+total=(?P<total>\d+)\s*-->"
)


def marked_rows(text: str) -> dict[str, bool]:
    """Every marked row in `text`, as key → *does this row say it is built*."""
    return {match["key"]: match["state"] == "built" for match in _ROW.finditer(text)}


def declared() -> dict[str, bool]:
    """What the screen itself is built from, as key → built."""
    return {setting.key: setting.built for setting in REQ_023_SETTINGS}


def disagreements(recorded: dict[str, bool], where: str) -> list[str]:
    """Every way `recorded` differs from the declaration, **named with its route** (`T-214`).

    `T-214`'s corrected guard reports *which* route disagrees rather than only that a rule was
    broken, and that is why its third defect was caught immediately rather than after a reading.
    """
    truth = declared()
    problems = [
        f"{where} does not mention {key!r}, which the screen declares as "
        f"{'built' if built else 'not built'}"
        for key, built in truth.items()
        if key not in recorded
    ]
    problems += [
        f"{where} records {key!r}, which the screen does not declare at all"
        for key in recorded
        if key not in truth
    ]
    problems += [
        f"{where} says {key!r} is {'built' if recorded[key] else 'not built'}, and the screen "
        f"says it is {'built' if truth[key] else 'not built'}"
        for key in recorded
        if key in truth and recorded[key] != truth[key]
    ]
    return problems


@pytest.fixture
def screen(qapp: QApplication, tmp_path: Path) -> Iterator[SettingsDialog]:
    """The real screen, built the way composition builds it."""
    built = SettingsDialog(
        download_directory=tmp_path / "downloads",
        directory_is_default=True,
        theme="light",
        concurrency=3,
        on_directory_chosen=lambda _value: None,
        on_theme_chosen=lambda _value: None,
        on_concurrency_chosen=lambda _value: None,
        on_network_chosen=lambda _value: None,
        preset_names=("Best video up to 1080p (MP4)",),
        on_default_preset_chosen=lambda _value: None,
        on_output_template_chosen=lambda _value: None,
    )
    yield built
    built.close()
    QApplication.processEvents()


def test_every_setting_this_screen_claims_is_actually_on_it(screen: SettingsDialog) -> None:
    """**A control name rather than a boolean**, so the declaration is checkable (`T-227`).

    A boolean is a claim; a name is something the built screen can be asked about. A setting
    declared built whose control is absent fails here — in the layer that knows — rather than
    turning into a document that is confidently wrong.
    """
    missing = {
        setting.key: setting.control
        for setting in REQ_023_SETTINGS
        if setting.built and screen.findChild(QWidget, setting.control) is None
    }

    assert not missing, (
        f"these settings are declared built and their controls are not on the screen: {missing}"
    )


def test_the_screens_sentence_is_derived_from_the_declaration() -> None:
    """The sentence cannot disagree with what is built, because it is not written down (`T-146`).

    Before this it was a hand-maintained sentence beside a hand-maintained screen, agreeing only
    for as long as somebody remembered both — and `T-195` is the day they stopped agreeing.
    """
    unbuilt = [setting.name for setting in REQ_023_SETTINGS if not setting.built]

    for name in unbuilt:
        assert name in SETTINGS_STILL_TO_COME, (
            f"{name!r} is not built and the screen does not say so: {SETTINGS_STILL_TO_COME!r}"
        )
    if not unbuilt:
        assert SETTINGS_STILL_TO_COME == "", (
            f"every setting is built and the screen still claims otherwise: "
            f"{SETTINGS_STILL_TO_COME!r}"
        )


def test_the_developer_table_agrees_with_the_screen() -> None:
    """**`docs/DEVELOPMENT.md`'s coverage table, read by marker rather than by prose** (`T-227`).

    This is the record `T-195` left saying two settings it had just built were *not built*, hours
    after approval, with every gate green. The markers are what make it checkable; the sentences
    around them stay free to be rewritten.
    """
    problems = disagreements(marked_rows(DEVELOPMENT.read_text(encoding="utf-8")), "DEVELOPMENT.md")

    assert not problems, "the coverage table and the screen disagree:\n  " + "\n  ".join(problems)


def test_the_ux_spec_count_agrees_with_the_screen() -> None:
    """**`docs/UX_SPEC.md` §2's count**, which is the number that rotted twice.

    A count is the most compressible form of this fact and therefore the most tempting to write in
    prose — *"the three `REQ-023` settings this phase built"* was wrong within a day. One marker
    carries both halves, so a partial update fails rather than half-passing.
    """
    text = UX_SPEC.read_text(encoding="utf-8")
    match = _COUNT.search(text)

    assert match is not None, (
        "docs/UX_SPEC.md carries no req023:count marker, so its count is ungated. If the sentence "
        "moved, move the marker with it"
    )
    built = len([setting for setting in REQ_023_SETTINGS if setting.built])
    assert (int(match["built"]), int(match["total"])) == (built, len(REQ_023_SETTINGS)), (
        f"UX_SPEC.md says {match['built']} of {match['total']} settings are built; the screen "
        f"declares {built} of {len(REQ_023_SETTINGS)}"
    )


def test_a_setting_built_without_touching_the_documents_is_caught() -> None:
    """**The mutation this whole gate exists to fail**, performed rather than argued (`T-227`).

    Not *"change the number"* — that is the shape `T214-R1` warns about, a guard proved against
    one spelling. The sequence that produced this task is **a setting is added to the screen and
    no document is updated**, and this performs exactly that: a ninth setting, declared built,
    with both documents left alone.

    Asserted through the same comparison the real gates use, so it cannot pass by testing a
    different function from the one that runs.
    """
    ninth = Req023Setting("sponsorblock", "SponsorBlock", "someControlThatWouldExist")
    recorded = marked_rows(DEVELOPMENT.read_text(encoding="utf-8"))
    truth = {**declared(), ninth.key: ninth.built}

    problems = [f"DEVELOPMENT.md does not mention {key!r}" for key in truth if key not in recorded]

    assert problems, (
        "a ninth setting was declared built, both documents were left untouched, and the gate "
        "found nothing — which is exactly the sequence T-227 was filed for"
    )
    assert "sponsorblock" in problems[0]


def test_a_document_that_disagrees_names_what_and_where() -> None:
    """**The gate names the route, not only that a rule was broken** (`T-214`'s corrected guard).

    A failure that says *"the documents are out of date"* sends the reader to read all of them.
    This one says which key, which document, and which way round.
    """
    stale = {setting.key: setting.built for setting in REQ_023_SETTINGS}
    stale["network-options"] = False

    problems = disagreements(stale, "DEVELOPMENT.md")

    assert len(problems) == 1
    assert "network-options" in problems[0]
    assert "DEVELOPMENT.md" in problems[0]
    assert "not built" in problems[0] and "is built" in problems[0]


def test_the_sentence_names_a_setting_that_is_not_built() -> None:
    """**The derivation, fed a declaration with a gap in it** (`T-227`).

    With all eight built the live sentence is empty, and an empty answer is what a *broken*
    derivation returns too — a mutation replacing the body with `return ""` survived the first
    sweep for exactly that reason. So this feeds it the state the sentence exists for, which is
    also the state the screen will be in the day `REQ-023` gains a ninth setting.
    """
    mixed = (
        Req023Setting("theme", "the theme", "themeLight"),
        Req023Setting("sponsorblock", "SponsorBlock", ""),
        Req023Setting("chapters", "chapter marks", ""),
    )

    sentence = still_to_come(mixed)

    assert "SponsorBlock" in sentence and "chapter marks" in sentence, (
        f"the sentence does not name what is missing: {sentence!r}"
    )
    assert "the theme" not in sentence, f"it names something that is built: {sentence!r}"
    assert still_to_come(mixed[:1]) == "", "a fully built declaration still claims something"


@pytest.mark.parametrize("document", [DEVELOPMENT, UX_SPEC], ids=lambda p: p.name)
def test_no_marker_starts_a_line_it_shares_with_prose(document: Path) -> None:
    """**`T227-R1`.** A marker at column one starts a CommonMark **raw-HTML block**.

    The whole line is then emitted without inline Markdown parsing, so the paragraph above it ends
    early and the rest of the line renders its backticks and asterisks literally — which is the
    opposite of an invisible marker, and it damaged the very sentence the marker exists to protect.
    The regex gates could not see it: they read the file as text and never asked where the comment
    sat.

    **A structural rule rather than a rendered one**, deliberately: parsing Markdown here would add
    a runtime dependency to a gate whose whole point is to be cheap and total. Two placements are
    safe and both are allowed — inline with prose around it, or alone on its own line.
    """
    offenders = [
        (number, line)
        for number, line in enumerate(document.read_text(encoding="utf-8").splitlines(), start=1)
        if line.startswith("<!--") and line.rstrip() != line[: line.index("-->") + 3].rstrip()
    ]

    assert not offenders, (
        f"{document.name} has a marker starting a line it shares with prose, which begins a "
        "CommonMark HTML block and swallows the rest of that line:\n  "
        + "\n  ".join(f"line {number}: {line[:90]}" for number, line in offenders)
    )
