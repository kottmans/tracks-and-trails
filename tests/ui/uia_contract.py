"""What a published accessibility tree must satisfy, separated from how one is read.

**Why this is not inside `test_windows_accessibility.py`.** That module calls
`pytest.skip(allow_module_level=True)` on anything but Windows, so every assertion it defines is
unreachable on the platform this project develops and reviews on. `P4EXIT-R1` found the cost:
the combo purpose check gathered *every* `ListItem` name under a dialog and asked whether any
combo was named one of them — which passes for a tree containing a combo named
`Best video available` and no list items at all, and never associates a name with **that combo's**
selection. Nobody could have run the counterexample, because nobody could import the assertion.

So the contract lives here, in plain data, and `tests/ui/test_uia_contract.py` hands it
constructed trees — including the reviewer's counterexample — on whatever platform is running.
The Windows module keeps every line that touches COM, and supplies real trees to the same
functions.

**What this module is not.** Proving an assertion rejects a constructed counterexample is not
evidence that Windows publishes anything in particular. The two halves answer different questions
and `docs/project/TESTING.md` §9 keeps them apart: this one is *"the check would catch it"*, and
only a Windows run answers *"the application does it"*.
"""

from __future__ import annotations

from dataclasses import dataclass

#: UI Automation control type IDs (`UIAutomationCore.h`). Spelled out rather than imported,
#: because the generated comtypes module names them inconsistently across versions — and because
#: this module must import on a machine that has no `UIAutomationCore.dll` to generate from.
UIA_WINDOW = 50032
UIA_MENU_BAR = 50010
UIA_MENU_ITEM = 50011
UIA_BUTTON = 50000
UIA_TITLE_BAR = 50037

#: **The run control is a `CheckBox`, not a `Button`** (`T-235`, measured 2026-08-12 after the
#: Windows job proved it). Qt gives a *checkable* `QToolButton` the accessible role `CheckBox`, and
#: UI Automation carries that through — so the queue's `Start`/`Stop` control has never been in
#: reach of a sweep scoped to buttons and menu items. That is a second hole in the same criterion,
#: found by the first one being fixed.
UIA_CHECKBOX = 50002

# **The editing roles, added by `P4EXIT-R1`.** The name sweep was scoped to menu items, buttons
# and check boxes — the roles the *main window* happened to have. Phase 4 added Settings and the
# add dialog, whose controls are edits, combo boxes, spin boxes, lists and tables, so the
# *"every interactive control"* the sweep claims stopped being true the moment those screens
# existed. `T-235` is the same finding one role earlier: a role nobody had thought of is a control
# nobody swept.
UIA_EDIT = 50004
UIA_COMBOBOX = 50003
UIA_SPINNER = 50016
UIA_LIST = 50008
UIA_LIST_ITEM = 50007
UIA_TABLE = 50036
UIA_RADIO_BUTTON = 50013
UIA_TAB_ITEM = 50019

#: Every role a user operates, which is what `NFR-005` is about.
OPERABLE_TYPES = (
    UIA_MENU_ITEM,
    UIA_BUTTON,
    UIA_CHECKBOX,
    UIA_EDIT,
    UIA_COMBOBOX,
    UIA_SPINNER,
    UIA_LIST,
    UIA_TABLE,
    UIA_RADIO_BUTTON,
    UIA_TAB_ITEM,
)

#: Role names, for failure messages a reader can interpret without a lookup table.
#:
#: **Every role this module names is in here** — `test_uia_contract.py` asserts that, because a
#: failure message reading `50016:''` is a failure message nobody can act on, and the previous
#: version of this table stopped at the six roles that existed before Phase 4.
ROLE_NAMES = {
    UIA_WINDOW: "Window",
    UIA_MENU_BAR: "MenuBar",
    UIA_MENU_ITEM: "MenuItem",
    UIA_BUTTON: "Button",
    UIA_CHECKBOX: "CheckBox",
    UIA_TITLE_BAR: "TitleBar",
    UIA_EDIT: "Edit",
    UIA_COMBOBOX: "ComboBox",
    UIA_SPINNER: "Spinner",
    UIA_LIST: "List",
    UIA_LIST_ITEM: "ListItem",
    UIA_TABLE: "Table",
    UIA_RADIO_BUTTON: "RadioButton",
    UIA_TAB_ITEM: "TabItem",
}


#: Contributed by the native title bar, not by this application.
#:
#: `ElementFromHandle` on a top-level window returns the whole frame, so the tree also carries
#: Windows' own System menu and the Minimize/Maximize/Close buttons. Asserting over everything
#: therefore asserts Windows' furniture as much as ours.
#:
#: Furniture is identified by **parentage**, via `Node.is_title_bar_furniture` — not by name.
#: An earlier version excluded the System menu by matching the string `"System"`, which is both
#: locale-dependent and unable to distinguish the About dialog's `Close` button from the title
#: bar's, since those share a name *and* a role. This constant is only the positive check that
#: the furniture is present and announced.
TITLE_BAR_BUTTONS = frozenset({"Minimize", "Maximize", "Close"})

#: Qt's own furniture, which Qt creates and leaves unnamed, and which this project does not own.
#:
#: **One list, read by both platforms' sweeps** (`T238-R5`). It belonged to
#: `tests/ui/test_accessibility.py` alone; that file now imports it from here. A second copy is
#: the copy that drifts, and the drift is invisible to both readers — which is what that task
#: recorded as the cost.
#:
#: Matched by Qt object name. On Linux that is `QWidget.objectName()` directly; on Windows it is
#: `UIA_AutomationIdPropertyId`, which Qt's bridge populates **from** the object name, so the same
#: string identifies the same widget through either tree.
#:
#: `qt_toolbar_ext_button` is the `»` overflow a `QToolBar` grows when it runs out of room, and
#: `qt_menubar_ext_button` its menu-bar twin. Both are Qt's widgets, created and destroyed by Qt,
#: and neither carries an accessible name in any application. **Named here rather than skipped
#: silently**, because *"the platform leaves this unnamed"* and *"we forgot to label this"* are
#: different facts, and a sweep that cannot tell them apart is a sweep nobody will trust the next
#: time it goes red.
PLATFORM_FURNITURE = frozenset(
    {
        "qt_toolbar_ext_button",
        "qt_menubar_ext_button",
        # A `QTableView`'s select-all corner, between the two headers. Qt builds it, Qt leaves it
        # unnamed and mouse-only, and the rows and columns it selects are reachable through the
        # table itself — which is the table's own keyboard contract, not one this project sets.
        "qt_tableview_cornerbutton",
    }
)


@dataclass(frozen=True)
class Node:
    """One accessibility element, reduced to the data a screen reader would use.

    `ancestor_roles` is what makes the contract non-vacuous (`T026-R2`, second round). A flat
    name-and-role list cannot tell the application's menu bar from the one Windows puts in the
    title bar, nor the About dialog's Close button from the title bar's — both pairs share a
    name and a role. The reviewer's adversarial harness passed the old checks using nothing but
    native furniture. Position in the tree is the distinguishing fact, so it is recorded.
    """

    name: str
    control_type: int

    #: Control types of every ancestor, nearest first, up to but excluding the queried root.
    ancestor_roles: tuple[int, ...] = ()

    #: What the element *holds*, from `ValuePattern` — `""` where it holds nothing or supports no
    #: such pattern (`P4EXIT-R1`).
    #:
    #: **Read so a name can be compared with its own control's value.** Whether Qt's Windows
    #: bridge populates this for a non-editable combo box is **unmeasured** — `P4EXIT-R2` is why
    #: nothing here has run on Windows. The check that uses it therefore engages per control only
    #: where a value arrives, and never carries the floor on its own; `displayed_values` does
    #: that, and comes from the live widgets.
    value: str = ""

    #: `UIA_AutomationIdPropertyId`, which Qt's Windows bridge fills from `QWidget.objectName()`.
    #:
    #: The only handle a published tree gives on *which widget* a node is, and the one
    #: `PLATFORM_FURNITURE` matches on. Without it the toolbar's `»` overflow — a `QToolButton`
    #: Qt publishes with the `CheckBox` role and no name — is indistinguishable from a control
    #: this project forgot to label.
    automation_id: str = ""

    @property
    def is_title_bar_furniture(self) -> bool:
        """Whether Windows contributed this, rather than the application."""
        return UIA_TITLE_BAR in self.ancestor_roles

    @property
    def is_owned_by_a_combo_box(self) -> bool:
        """Whether Qt built this *inside* a combo box, rather than this project placing it.

        A `QComboBox` publishes its dropdown `QListView` as its own child, unnamed — measured on
        this project's Settings screen and add dialog, four instances. It is Qt's widget and Qt's
        to name; requiring a name there would assert something the toolkit does not do, and the
        only way to make it pass would be to weaken the rule for everything else.

        **Derived from `ancestor_roles`, which the tree already carries**, rather than from a list
        of names — the popup has no object name to list, and parentage is what distinguishes it.
        That is the same discriminator `test_accessibility.py` uses on the Qt side, where the fact
        available is the parent widget's class.
        """
        return UIA_COMBOBOX in self.ancestor_roles

    @property
    def is_platform_furniture(self) -> bool:
        """Whether Qt or Windows contributed this node, rather than this application."""
        return (
            self.is_title_bar_furniture
            or self.is_owned_by_a_combo_box
            or self.automation_id in PLATFORM_FURNITURE
        )


@dataclass(frozen=True)
class Tree:
    """A window and everything beneath it, as UI Automation publishes it."""

    window: Node
    descendants: tuple[Node, ...]

    def of_type(self, control_type: int) -> tuple[Node, ...]:
        return tuple(node for node in self.descendants if node.control_type == control_type)

    def application_controls(self) -> tuple[Node, ...]:
        """Everything the application owns — the tree minus Windows' and Qt's own furniture.

        Every assertion about *this project's* accessibility goes through here. Asserting over
        `descendants` lets Windows' own controls satisfy the contract, which is exactly how the
        previous version could pass with no `File` or `Help` at all.

        **It excluded the title bar's subtree and nothing else until `P4EXIT-R1`.** Replaying the
        new sweep against Qt's own published tree found the gap immediately: four unnamed combo
        dropdown lists across Settings and the add dialog, and the toolbar's `»` overflow button,
        every one of them Qt's. A name sweep that fails on the toolkit's furniture is a sweep that
        gets weakened, not one that gets fixed.
        """
        return tuple(node for node in self.descendants if not node.is_platform_furniture)


def describe(nodes: tuple[Node, ...]) -> list[str]:
    """Render a tree for a failure message: what Narrator would actually encounter."""
    return [f"{ROLE_NAMES.get(n.control_type, n.control_type)}:{n.name!r}" for n in nodes]


def named_operable(subtree: Tree) -> tuple[Node, ...]:
    """The application's own operable controls in `subtree`, title-bar furniture excluded."""
    return tuple(
        node for node in subtree.application_controls() if node.control_type in OPERABLE_TYPES
    )


def assert_every_control_is_named(subtree: Tree, screen: str) -> tuple[Node, ...]:
    """`NFR-005` over one screen's published tree, with a non-vacuity floor.

    **The floor is the half that matters** (`T-227`'s lesson, restated by `P4EXIT-R1`). A screen
    that fails to open, or that publishes nothing to UI Automation, yields an empty list — and
    *"no unnamed controls"* is trivially true of nothing. Both halves are asserted here so no
    caller can satisfy one and skip the other.
    """
    operable = named_operable(subtree)
    assert operable, (
        f"the {screen} publishes no operable control to UI Automation at all, so a name sweep "
        f"over it would pass by looking at nothing. Full subtree: {describe(subtree.descendants)}"
    )
    unnamed = tuple(node for node in operable if not node.name.strip())
    assert not unnamed, (
        f"{len(unnamed)} control(s) on the {screen} expose no accessible name to Narrator: "
        f"{describe(unnamed)}"
    )
    return operable


def _heard_as(text: str) -> str:
    """One spelling of `text`, the way a listener would not distinguish it."""
    return " ".join(text.split()).casefold()


def assert_combos_announce_their_purpose(
    subtree: Tree, screen: str, *, displayed_values: frozenset[str]
) -> tuple[Node, ...]:
    """A combo box announces what it **is for**, never merely what it currently holds.

    *"Best video available"* is what the batch preset control holds; *"Preset"* is what it is. A
    user tabbing onto it hears the former and has to infer the latter, which is the difference
    between a labelled control and a value read aloud. This project has met the failure on the
    other platform: `T200-R7` records `QAccessibleComboBox::text` falling through `Name` to
    `Value` under `Q_OS_UNIX`, discarding `setAccessibleName`, which is why `ui/options_dialog.py`
    and `ui/settings_dialog.py` carry buddy labels.

    **Three assertions, and `displayed_values` is the one that carries the weight** (`P4EXIT-R1`):

    1. Every combo has a name at all — the *missing purpose* case.
    2. No combo is named its **own** `value`. Per control and exact, but it engages only where the
       platform publishes a value, so it is a strengthening and never the floor.
    3. No combo is named any value this screen is **actually displaying**. `displayed_values` is
       read from the live widgets by the caller, so it is non-empty by construction and is
       asserted to be — which is precisely what the superseded version lacked. It gathered every
       `ListItem` in the published tree, required none to exist, and tied none of them to a
       particular combo; a tree with one combo named `Best video available` and no list items
       passed it unchanged.

    Checks 2 and 3 overlap deliberately. Where a value arrives, 2 names the offending control
    exactly; 3 holds whether or not one does.
    """
    combos = tuple(
        node for node in subtree.application_controls() if node.control_type == UIA_COMBOBOX
    )
    assert combos, (
        f"the {screen} published no combo box, so this asserts nothing; the screen has several "
        f"and one of them should be here. Found: {describe(subtree.application_controls())}"
    )

    unnamed = tuple(node for node in combos if not node.name.strip())
    assert not unnamed, (
        f"{len(unnamed)} combo box(es) on the {screen} publish no name at all, so Narrator "
        f"announces a role and nothing else: {describe(combos)}"
    )

    named_for_own_value = tuple(
        node
        for node in combos
        if node.value.strip() and _heard_as(node.name) == _heard_as(node.value)
    )
    assert not named_for_own_value, (
        f"combo box(es) on the {screen} are named exactly what they hold, so Narrator repeats "
        "the selection where the purpose belongs: "
        + ", ".join(f"{n.name!r} holding {n.value!r}" for n in named_for_own_value)
    )

    assert displayed_values, (
        f"the caller supplied no displayed values for the {screen}, so check 3 below compares "
        "against an empty set and passes over anything. Read them from the live combo boxes"
    )
    heard = {_heard_as(value) for value in displayed_values if value.strip()}
    assert heard, (
        f"every displayed value on the {screen} is blank, which leaves nothing to compare a name "
        f"against: {sorted(displayed_values)}"
    )
    named_for_a_value = tuple(node for node in combos if _heard_as(node.name) in heard)
    assert not named_for_a_value, (
        f"combo box(es) on the {screen} announce a value this screen is displaying where their "
        f"purpose belongs, so Narrator says what is selected and never what it is for: "
        f"{describe(named_for_a_value)}. Values on display: {sorted(heard)}"
    )
    return combos
