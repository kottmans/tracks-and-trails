"""Counterexamples for the published-tree contract, run on whatever platform is present.

**This file exists because `P4EXIT-R1` found an assertion that passed a tree it should have
rejected, and nobody could have run the counterexample.** The check lived inside
`test_windows_accessibility.py`, which skips at module level on anything but Windows, so the only
way to demonstrate its defect was to copy it into a temporary harness — which is what the
reviewer did. The pure half now lives in `tests/ui/uia_contract.py` and the harness is kept.

**What a pass here does and does not establish.** It establishes that the contract rejects a
tree with a missing name, a value read as a name, or nothing in it at all: *the check would catch
it*. It establishes nothing whatever about what Windows publishes — that is `P4EXIT-R2`'s
outstanding evidence, and `docs/project/TESTING.md` §9 keeps the two apart. Every tree below is
hand-built; none came from UI Automation.

**Why the negative cases outnumber the positive one.** A gate is only as good as the thing it
refuses, and this project has now recorded five checks that passed their own defect (`T-227`,
`T-201`, `T-314`, `T290-R1`, `T286-R1`). Each `pytest.raises` below is one of those, pre-empted.
"""

from __future__ import annotations

import pytest

from tests.ui.uia_contract import (
    OPERABLE_TYPES,
    PLATFORM_FURNITURE,
    ROLE_NAMES,
    UIA_BUTTON,
    UIA_CHECKBOX,
    UIA_COMBOBOX,
    UIA_EDIT,
    UIA_LIST,
    UIA_LIST_ITEM,
    UIA_MENU_BAR,
    UIA_TITLE_BAR,
    UIA_WINDOW,
    Node,
    Tree,
    assert_combos_announce_their_purpose,
    assert_every_control_is_named,
    named_operable,
)

#: The value the reviewer's counterexample used, and a real one: it is what the batch preset
#: control on the add dialog displays.
A_DISPLAYED_VALUE = "Best video available"


def tree(*nodes: Node) -> Tree:
    """A window with `nodes` beneath it."""
    return Tree(window=Node(name="Tracks and Trails", control_type=UIA_WINDOW), descendants=nodes)


# --- the name sweep ---------------------------------------------------------------------------


def test_a_screen_that_publishes_nothing_cannot_satisfy_the_name_sweep() -> None:
    """`T-227`'s defect, as a counterexample. *"No unnamed controls"* is true of no controls.

    This is the shape a fixture failure takes: a screen that never opened publishes an empty
    tree, and a sweep without a floor calls that a pass. `P4EXIT-R1` requirement 1 is the same
    fault one layer up — three tests whose window could not open the screens they audited.
    """
    with pytest.raises(AssertionError, match="publishes no operable control"):
        assert_every_control_is_named(tree(), "an empty screen")


def test_a_screen_of_static_text_alone_cannot_satisfy_the_name_sweep() -> None:
    """Nodes that exist but are not operable are not controls, so they are not the floor."""
    label = Node(name="Download to", control_type=50020)  # UIA_Text
    with pytest.raises(AssertionError, match="publishes no operable control"):
        assert_every_control_is_named(tree(label), "a screen of labels")


def test_an_unnamed_control_fails_the_name_sweep() -> None:
    """`NFR-005`. A button Narrator cannot name is a button a user cannot choose."""
    with pytest.raises(AssertionError, match="expose no accessible name"):
        assert_every_control_is_named(
            tree(
                Node(name="Cancel", control_type=UIA_BUTTON),
                Node(name="   ", control_type=UIA_BUTTON),
            ),
            "a screen with a nameless button",
        )


def test_a_named_control_of_every_operable_role_passes() -> None:
    """The positive control: the sweep is not merely always failing.

    Covers **every** role in `OPERABLE_TYPES` rather than one of them — a sweep that recognised
    only buttons would pass a one-button case and still be the `T-235` defect. Recalled from
    *"mutate every instance the constant claims"*: one example proves one case, not the property.
    """
    named = tuple(Node(name=f"Control {role}", control_type=role) for role in OPERABLE_TYPES)
    assert len(assert_every_control_is_named(tree(*named), "a fully named screen")) == len(
        OPERABLE_TYPES
    )


def test_title_bar_furniture_cannot_satisfy_the_floor() -> None:
    """`T026-R2`. Windows' own Close button is not this application publishing a control.

    Without this, every screen passes the floor on furniture the project did not write — which is
    exactly how the superseded menu-bar check passed with no `File` or `Help` in the tree.
    """
    windows_own = Node(
        name="Close", control_type=UIA_BUTTON, ancestor_roles=(UIA_TITLE_BAR, UIA_WINDOW)
    )
    assert not named_operable(tree(windows_own))
    with pytest.raises(AssertionError, match="publishes no operable control"):
        assert_every_control_is_named(tree(windows_own), "a screen with only furniture")


def test_a_combo_boxs_own_dropdown_cannot_fail_the_name_sweep() -> None:
    """Qt publishes a `QComboBox`'s popup list as its child, unnamed, and it is Qt's to name.

    **Measured, not assumed** (`P4EXIT-R1`): replaying this sweep against Qt's own published tree
    found four of them — two on Settings, two on the add dialog — every one a `QListView` directly
    beneath a `ComboBox`. A rule that fails on the toolkit's furniture is a rule that gets
    weakened rather than fixed, which is how a name sweep stops meaning anything.
    """
    popup = Node(name="", control_type=UIA_LIST, ancestor_roles=(UIA_COMBOBOX, UIA_WINDOW))
    real = Node(name="Preset", control_type=UIA_COMBOBOX, ancestor_roles=(UIA_WINDOW,))
    assert popup.is_platform_furniture
    assert not real.is_platform_furniture
    assert assert_every_control_is_named(tree(real, popup), "a screen with a combo") == (real,)


#: What Qt's Windows bridge actually publishes for this application's toolbar overflow button.
#:
#: **Measured, not invented** (`P4EXIT-R1`, third pass). Qt 6.11.1's provider obtains `AutomationId`
#: from `QAccessibleBridgeUtils::accessibleId`, which builds a dot-separated path through the
#: accessible ancestors. Replaying that algorithm over the composed main window on Linux yields
#: exactly this string — the same one the reviewer derived independently from the pinned provider
#: source.
MEASURED_OVERFLOW_ID = "QApplication.mainWindow.queueToolBar.qt_toolbar_ext_button"


def _qualified(own_name: str) -> str:
    """A realistic bridge identifier for a widget named `own_name`, in the shape Qt publishes."""
    return f"QApplication.mainWindow.queueToolBar.{own_name}"


def test_the_measured_overflow_identifier_is_recognised_as_furniture() -> None:
    """**The defect the third pass found**, as the string the bridge really publishes.

    `is_platform_furniture` compared the *whole* `automation_id` against bare object names, and Qt
    does not publish bare object names. So the exclusion never fired: replaying the all-surfaces
    sweep with this representation failed at the **first** surface, the main window, on this very
    control — an unnamed `CheckBox`, because Qt gives a checkable `QToolButton` that role
    (`T-235`).

    The superseded predicate is reconstructed below so this is shown to be a counterexample rather
    than asserted to be one.
    """
    overflow = Node(name="", control_type=UIA_CHECKBOX, automation_id=MEASURED_OVERFLOW_ID)

    assert MEASURED_OVERFLOW_ID not in PLATFORM_FURNITURE, (
        "the superseded predicate compared the whole identifier against the allowlist, and this "
        "is what it was handed — the comparison could not succeed"
    )
    assert overflow.is_platform_furniture, MEASURED_OVERFLOW_ID
    with pytest.raises(AssertionError, match="publishes no operable control"):
        assert_every_control_is_named(tree(overflow), "a toolbar that overflowed")


def test_every_allowlisted_widget_is_recognised_through_a_qualified_identifier() -> None:
    """**All three**, not the one this application happens to show (`P4EXIT-R1`).

    Only `qt_toolbar_ext_button` appears in this project's measured tree. The other two are
    exercised in the shape the bridge would publish them in, which is what the allowlist claims to
    cover — *"mutate every instance the constant claims"*: one example proves one case, not the
    property. These two identifiers are realistic, not observed, and this docstring says so rather
    than letting the test imply a measurement.
    """
    for own_name in sorted(PLATFORM_FURNITURE):
        node = Node(name="", control_type=UIA_CHECKBOX, automation_id=_qualified(own_name))
        assert node.is_platform_furniture, _qualified(own_name)
        with pytest.raises(AssertionError, match="publishes no operable control"):
            assert_every_control_is_named(tree(node), f"a screen showing {own_name}")


def test_an_explicit_accessible_identifier_is_still_recognised() -> None:
    """The other shape `accessibleId` returns: a declared `QAccessible::Identifier`, with no path.

    Qt uses an explicit identifier verbatim when a widget declares one, so a bare allowlist name is
    a genuine possibility rather than a leftover from the superseded comparison. One rule covers
    both shapes because it takes the last segment, and a string with no dot is its own last
    segment.
    """
    for own_name in sorted(PLATFORM_FURNITURE):
        assert Node(
            name="", control_type=UIA_CHECKBOX, automation_id=own_name
        ).is_platform_furniture


@pytest.mark.parametrize(
    "identifier",
    [
        # A control whose own name merely *ends with* an allowlisted one.
        _qualified("myqt_toolbar_ext_button"),
        _qualified("qt_toolbar_ext_button_2"),
        # An allowlisted widget's own child. The furniture is the button, not everything under it.
        f"{MEASURED_OVERFLOW_ID}.QLabel",
        # The name in an ancestor segment rather than the widget's own.
        "QApplication.qt_toolbar_ext_button.chooseFolderButton",
        # And a control this project owns, which was never furniture.
        "QApplication.settingsDialog.chooseFolderButton",
    ],
)
def test_a_lookalike_identifier_is_not_excused(identifier: str) -> None:
    """**The exclusion must not grow.** A hole that widens is one nobody notices widening.

    Each of these would be excused by a suffix or substring test, and none of them is a widget Qt
    owns. The last-segment comparison is what refuses them, and these are the cases that keep it
    from being loosened into one.
    """
    node = Node(name="", control_type=UIA_BUTTON, automation_id=identifier)
    assert not node.is_platform_furniture, identifier
    with pytest.raises(AssertionError, match="expose no accessible name"):
        assert_every_control_is_named(
            tree(Node(name="Cancel", control_type=UIA_BUTTON), node), "a screen with one of these"
        )


def test_an_unnamed_control_this_project_owns_is_not_excused_by_either_rule() -> None:
    """The negative control for both exclusions above, which is the half that can rot.

    An exclusion is a hole in a gate, and a hole that grows is one nobody notices. This is the
    assertion that the two rules above still refuse an ordinary unnamed button.
    """
    ours = Node(name="", control_type=UIA_BUTTON, automation_id="chooseFolderButton")
    assert not ours.is_platform_furniture
    with pytest.raises(AssertionError, match="expose no accessible name"):
        assert_every_control_is_named(
            tree(Node(name="Cancel", control_type=UIA_BUTTON), ours), "Settings screen"
        )


# --- the combo purpose check (`P4EXIT-R1` requirement 3) ----------------------------------------


def test_the_reviewers_counterexample_is_rejected() -> None:
    """**The exact tree the superseded check passed**, which is why this file exists.

    `P4EXIT-R1`: *"A constructed tree containing a combo named `Best video available` and no
    ListItem passes the new test unchanged."* It did, because the check compared the name against
    the set of `ListItem` names in the tree and never required that set to be non-empty — an
    empty set makes *"the name is not one of these"* true of every name there is.

    The floor is now `displayed_values`, read from the live widgets by the caller, so the
    comparison is against what the screen is genuinely showing rather than against whatever
    happens to be in the published tree.
    """
    published = tree(Node(name=A_DISPLAYED_VALUE, control_type=UIA_COMBOBOX))
    with pytest.raises(AssertionError, match="announce a value this screen is displaying"):
        assert_combos_announce_their_purpose(
            published, "Settings screen", displayed_values=frozenset({A_DISPLAYED_VALUE})
        )


def test_the_superseded_comparison_would_have_passed_that_tree() -> None:
    """The defect itself, reconstructed, so the counterexample above is shown to be one.

    A `pytest.raises` proves the new check rejects this tree. It does not prove the **old** one
    accepted it, and a correction that fixes a defect nobody demonstrated is a correction nobody
    can evaluate. This is the superseded expression, four lines of it, run against the same tree.
    """
    published = tree(Node(name=A_DISPLAYED_VALUE, control_type=UIA_COMBOBOX))
    combos = [n for n in published.application_controls() if n.control_type == UIA_COMBOBOX]
    values = {n.name.strip().casefold() for n in published.of_type(UIA_LIST_ITEM) if n.name.strip()}

    assert combos, "the old check's only floor: a non-empty combo list"
    assert not values, "and no list items at all, which is what made the comparison vacuous"
    assert not [n for n in combos if n.name.strip().casefold() in values], (
        "the superseded assertion passed this tree — a combo announcing nothing but its value"
    )


def test_a_combo_with_no_name_is_rejected() -> None:
    """The *missing purpose* half. Narrator announces a role and stops."""
    published = tree(
        Node(name="", control_type=UIA_COMBOBOX),
        Node(name="Preset", control_type=UIA_COMBOBOX),
    )
    with pytest.raises(AssertionError, match="publish no name at all"):
        assert_combos_announce_their_purpose(
            published, "Settings screen", displayed_values=frozenset({A_DISPLAYED_VALUE})
        )


def test_a_combo_named_its_own_value_is_rejected_per_control() -> None:
    """The per-control half, which engages wherever the platform publishes a value.

    Named for what **this** control holds, and the screen displays something else entirely — so
    the set comparison would miss it and only the per-node one catches it. That is why both are
    asserted rather than either.
    """
    published = tree(Node(name="MP4", control_type=UIA_COMBOBOX, value="MP4"))
    with pytest.raises(AssertionError, match="named exactly what they hold"):
        assert_combos_announce_their_purpose(
            published, "Options", displayed_values=frozenset({"Something else"})
        )


def test_whitespace_and_case_do_not_hide_a_value_read_as_a_name() -> None:
    """A listener does not hear capitalisation or a double space, so neither does this."""
    published = tree(Node(name="  best   VIDEO available ", control_type=UIA_COMBOBOX))
    with pytest.raises(AssertionError, match="announce a value this screen is displaying"):
        assert_combos_announce_their_purpose(
            published, "Settings screen", displayed_values=frozenset({A_DISPLAYED_VALUE})
        )


def test_a_screen_with_no_combo_is_rejected_rather_than_passed_over() -> None:
    """On a screen that has combos, an empty list means the query failed — not that it passed."""
    with pytest.raises(AssertionError, match="published no combo box"):
        assert_combos_announce_their_purpose(
            tree(Node(name="Cancel", control_type=UIA_BUTTON)),
            "Settings screen",
            displayed_values=frozenset({A_DISPLAYED_VALUE}),
        )


@pytest.mark.parametrize("supplied", [frozenset(), frozenset({""}), frozenset({"  "})])
def test_a_caller_supplying_no_displayed_values_is_rejected(supplied: frozenset[str]) -> None:
    """**The floor's own floor.** An empty comparison set passes every name there is.

    This is the defect one level down from the reviewer's counterexample: the correction replaces
    a set that could silently be empty with one that is asserted not to be. Without this case,
    a caller reading values from a screen whose combos had not been populated yet would restore
    the original vacuity and no test would notice.
    """
    published = tree(Node(name=A_DISPLAYED_VALUE, control_type=UIA_COMBOBOX))
    with pytest.raises(AssertionError, match=r"no displayed values|every displayed value"):
        assert_combos_announce_their_purpose(
            published, "Settings screen", displayed_values=supplied
        )


def test_a_combo_named_for_its_purpose_passes() -> None:
    """The positive control. A named combo holding a displayed value is correct, not suspect."""
    published = tree(
        Node(name="Preset", control_type=UIA_COMBOBOX, value=A_DISPLAYED_VALUE),
        Node(name="Container", control_type=UIA_COMBOBOX, value="MP4"),
        Node(name="Download to", control_type=UIA_EDIT),
    )
    combos = assert_combos_announce_their_purpose(
        published, "Settings screen", displayed_values=frozenset({A_DISPLAYED_VALUE, "MP4"})
    )
    assert [node.name for node in combos] == ["Preset", "Container"]


# --- the failure messages ----------------------------------------------------------------------


def test_every_role_the_contract_names_renders_as_a_word() -> None:
    """A message reading `50016:''` is one no reader can act on.

    `ROLE_NAMES` stopped at the six roles that existed before Phase 4, so the eight added for the
    editing screens would have printed as bare integers in exactly the failure a reader most
    needs to interpret.
    """
    missing = [
        role
        for role in (*OPERABLE_TYPES, UIA_WINDOW, UIA_MENU_BAR, UIA_TITLE_BAR, UIA_LIST_ITEM)
        if role not in ROLE_NAMES
    ]
    assert not missing, f"roles with no readable name: {missing}"
