"""What a screen reader actually reads on Windows (`T-026`, `NFR-005`, `OPS-004`).

Separate from `test_windows_desktop.py` on purpose. That file proves the window reaches a
desktop — Phase 0's exit criterion. This one asserts the accessibility tree, which is the part
`OPS-003` had classified as human-only. Keeping them apart means a UI Automation problem is
never mistaken for a launch problem.

**Why UI Automation and not `QAccessible`.** Qt exposes its own accessibility interface, and
asserting on it would be Qt reporting on Qt — it would pass even if the Windows bridge were
broken and Narrator heard nothing. UI Automation is the tree Windows itself publishes, which
is the data assistive technology consumes. That distinction is the whole point of `OPS-004`:
the objective half of accessibility is checkable, but only against the real thing.

**Why the queries run on a worker thread.** A UI Automation client inspecting its *own*
process must not call from the thread that owns the window. Qt's Windows accessibility bridge
is built lazily in response to `WM_GETOBJECT`, which the GUI thread has to handle — so a
synchronous UIA call made *from* the GUI thread blocks the very thread that must answer it.
The first CI run of this file did exactly that and showed the symptom precisely: an empty
descendant list and `COMError 0x80040201` from `CurrentName`. The queries therefore run in an
MTA worker thread while the main thread pumps the Qt event loop, and only plain data crosses
back — COM interface pointers are not thread-agnostic.

What this does **not** claim: that Narrator's announcements are *coherent*. A correct tree is
necessary and not sufficient, and the difference stays a human judgement (`docs/project/TESTING.md`
§9).
"""

import ctypes
import sys
import threading
import time
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QComboBox, QMenu, QWidget

from tests.ui.conftest import Surface, focusable
from tests.ui.uia_contract import (
    OPERABLE_TYPES,
    TITLE_BAR_BUTTONS,
    UIA_BUTTON,
    UIA_CHECKBOX,
    UIA_COMBOBOX,
    UIA_EDIT,
    UIA_MENU_BAR,
    UIA_MENU_ITEM,
    UIA_SPINNER,
    UIA_WINDOW,
    Node,
    Tree,
    assert_combos_announce_their_purpose,
    assert_every_control_is_named,
    describe,
    named_operable,
)
from tracks_and_trails.ui.main_window import APP_NAME, MainWindow

pytestmark = pytest.mark.windows_desktop

if sys.platform != "win32":
    pytest.skip("UI Automation is a Windows API", allow_module_level=True)

# Imported plainly, never via `importorskip`. On Windows comtypes is a declared dev dependency,
# so a failure to import is a broken environment, not a reason to opt out — and a skip here
# would delete the only automated accessibility gate while leaving the job green.
import comtypes  # noqa: E402
import comtypes.client  # noqa: E402

# **The role table, `Node`, `Tree` and every assertion over them now live in
# `tests/ui/uia_contract.py`** (`P4EXIT-R1`). They are plain data and pure functions, and keeping
# them behind this module's `allow_module_level=True` skip meant no counterexample to any of them
# could be run on the platform this project is developed and reviewed on. The reviewer had to
# extract them into a temporary harness to demonstrate the combo check passed a constructed tree
# it should have rejected. `tests/ui/test_uia_contract.py` is that harness, kept.
#
# What stays here is everything that touches COM: reading a real tree out of a real window.

#: `CLSID_CUIAutomation`.
CUIAUTOMATION = "{ff48dba4-60ef-4201-aa87-54103eef594e}"

#: Fails a malformed or cyclic tree instead of recursing until CI times out.
MAX_TREE_DEPTH = 32

#: Generous: the tree is tiny, but a first call has to build Qt's accessibility bridge and
#: generate the comtypes typelib wrapper. A timeout here fails the test rather than hanging CI.
QUERY_TIMEOUT_SECONDS = 30.0


#: `UIA_ValueValuePropertyId`. The value a control holds, where it holds one.
UIA_VALUE_PROPERTY = 30045

#: `UIA_AutomationIdPropertyId`. Qt's bridge fills it from `QWidget.objectName()`, which is how
#: `PLATFORM_FURNITURE` recognises the toolkit's own widgets through a published tree.
UIA_AUTOMATION_ID_PROPERTY = 30011


def _property(element: object, identifier: int) -> str:
    """One string property of `element`, or `""`.

    Asked through `GetCurrentPropertyValue` rather than by querying a pattern: an element that
    supports no such pattern answers empty rather than raising, which is the behaviour a sweep
    over every node needs. Any COM failure is treated as *"holds nothing"* for the same reason —
    these are fields of a diagnostic snapshot, not assertions in themselves.
    """
    try:
        raw = element.GetCurrentPropertyValue(identifier)  # type: ignore[attr-defined]
    except Exception:  # a missing pattern is a normal answer here, not a fault
        return ""
    return str(raw) if raw else ""


def _read_tree(hwnd: int) -> Tree:
    """Snapshot the UI Automation tree for `hwnd`. Runs on the calling (worker) thread.

    Walks the control view rather than calling `FindAll(TreeScope_Descendants)`: `FindAll`
    returns a flat collection with no parent information, and parentage is precisely what
    distinguishes an application control from title-bar furniture.
    """
    # COINIT_MULTITHREADED. A UIA client belongs in the MTA; an STA worker would reintroduce
    # the message-pump dependency this thread exists to escape.
    ctypes.windll.ole32.CoInitializeEx(None, 0)
    try:
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient

        automation = comtypes.client.CreateObject(
            CUIAUTOMATION, interface=UIAutomationClient.IUIAutomation
        )
        root = automation.ElementFromHandle(ctypes.c_void_p(hwnd))
        if root is None:
            raise AssertionError("UI Automation cannot see the window at all")

        walker = automation.ControlViewWalker
        collected: list[Node] = []

        def walk(element: object, ancestors: tuple[int, ...], depth: int) -> None:
            # A depth cap so a malformed or cyclic tree fails the test rather than hanging CI.
            if depth > MAX_TREE_DEPTH:
                raise AssertionError(f"accessibility tree deeper than {MAX_TREE_DEPTH} levels")
            child = walker.GetFirstChildElement(element)
            while child:
                role = child.CurrentControlType
                collected.append(
                    Node(
                        name=child.CurrentName or "",
                        control_type=role,
                        ancestor_roles=ancestors,
                        value=_property(child, UIA_VALUE_PROPERTY),
                        automation_id=_property(child, UIA_AUTOMATION_ID_PROPERTY),
                    )
                )
                walk(child, (role, *ancestors), depth + 1)
                child = walker.GetNextSiblingElement(child)

        walk(root, (), 0)
        return Tree(
            window=Node(name=root.CurrentName or "", control_type=root.CurrentControlType),
            descendants=tuple(collected),
        )
    finally:
        ctypes.windll.ole32.CoUninitialize()


def read_tree(hwnd: int) -> Tree:
    """Snapshot `hwnd`'s accessibility tree without blocking the GUI thread.

    The main thread keeps pumping Qt events for the duration, because that is what answers the
    `WM_GETOBJECT` the UIA client sends. Stop pumping and the query returns an empty tree.

    Takes an arbitrary handle rather than only the main window's, so menus and dialogs — which
    are their own top-level windows on Windows — can be queried too. `T026-R2`: the first
    version only ever looked at the main window, which is why a missing `Quit` action or an
    unlabelled About dialog could not have been detected.
    """
    result: dict[str, object] = {}

    def worker() -> None:
        try:
            result["tree"] = _read_tree(hwnd)
        except BaseException as error:
            # Caught broadly and re-raised on the main thread below. An exception escaping a
            # worker thread would otherwise be printed and discarded, leaving the caller to
            # report a timeout and hiding the real COM error underneath it.
            result["error"] = error

    thread = threading.Thread(target=worker, name="uia-query", daemon=True)
    thread.start()

    deadline = time.monotonic() + QUERY_TIMEOUT_SECONDS
    while thread.is_alive() and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    thread.join(timeout=1.0)

    if "error" in result:
        raise AssertionError(f"the UI Automation query failed: {result['error']!r}")
    if "tree" not in result:
        raise AssertionError(
            f"the UI Automation query did not finish within {QUERY_TIMEOUT_SECONDS}s"
        )
    snapshot = result["tree"]
    assert isinstance(snapshot, Tree)
    return snapshot


@pytest.fixture
def window(qapp: QApplication, tmp_path: Path) -> MainWindow:
    """A shown, activated main window — **with its toolbar** (`T-235`).

    **This built a bar-less window until 2026-08-12, and nobody noticed for a phase.** The gate
    below sweeps every button in the tree and requires a name on each, and its docstring says
    *"over every interactive control, not only the ones this file names"* — which was true of the
    tree it was handed and false of the application. `MainWindow` builds no toolbar without
    `control_bar` (`T-234` made that switch explicit; before, it was `concurrency`), so
    `+ Add URLs`, the run control and `Clear finished` were **never in the tree at all** and have
    never been checked for accessible names on Windows.

    `T-234`'s criteria asked for this file to be *"updated for the removal"* and it could not be:
    there was nothing here to update. `T234-R1` is that finding.
    """
    shown = MainWindow(geometry_file=tmp_path / "window.toml", control_bar=True)
    shown.show()
    shown.raise_()
    shown.activateWindow()
    QApplication.processEvents()
    return shown


@pytest.fixture
def tree(window: MainWindow) -> Tree:
    """The main window's accessibility tree."""
    return read_tree(int(window.winId()))


# --- the main window ------------------------------------------------------------------------


def test_the_window_is_published_with_its_name_and_role(tree: Tree) -> None:
    """The top-level element is what a screen reader announces on focus."""
    assert tree.window.name == APP_NAME, (
        f"UI Automation announces the window as {tree.window.name!r}"
    )
    assert tree.window.control_type == UIA_WINDOW


def test_the_application_publishes_its_own_menu_bar(tree: Tree) -> None:
    """`T026-R2`. The application's menu bar, not Windows'.

    The native title bar contributes a `MenuBar` of its own — the System menu. Asserting that
    *a* menu bar exists is therefore satisfied by furniture this project did not write, which
    is what the reviewer's adversarial harness demonstrated. The distinguishing fact is
    parentage, so the check is scoped to controls outside the title bar's subtree.
    """
    bars = [node for node in tree.application_controls() if node.control_type == UIA_MENU_BAR]
    assert len(bars) == 1, (
        f"expected exactly one application-owned menu bar, found {len(bars)}. "
        f"Application controls: {describe(tree.application_controls())}"
    )


def test_the_application_menu_bar_exposes_exactly_file_and_help(tree: Tree) -> None:
    """`T026-R2`. An **equality** over the application's own menu items.

    This assertion existed in the first correction round and was **deleted by accident** while
    reworking the neighbouring tests — a scripted block replacement spanned past it. Its
    absence is precisely why the suite could pass on native furniture alone. Restored here,
    and now scoped so the System menu cannot satisfy it.

    An equality rather than a subset: a subset stays green when a menu is added unlabelled,
    duplicated, or published under the wrong role.

    Mnemonic markup must not survive into the tree either — Qt strips `&` when publishing to
    the platform bridge, and a regression there has Narrator saying "ampersand File".

    **`Settings` joined the two for six hours on 2026-08-06 and left again**, and both halves are
    worth keeping. It arrived with `T-170` as the only route to *Clear download records*; this
    equality caught it, on the Windows job alone, after the Linux suite had passed and three more
    commits had been pushed — `AGENTS.md` §8's asymmetry working as intended. It went when `REQ-020`
    was withdrawn and the screen had nothing left in it.

    **It is back, and permanently this time** (`T-146`, 2026-08-10): the screen behind it holds the
    download folder, the theme and the concurrency limit that `REQ-023` names, so unlike `T-170`'s
    version it does not depend on a requirement that could be withdrawn under it. This equality
    tripped again on the same change, which is exactly what it is for — updating it is a deliberate
    act, and the list below is the whole of the application's menu bar.
    """
    items = [node for node in tree.application_controls() if node.control_type == UIA_MENU_ITEM]
    names = sorted(node.name for node in items)

    assert names == ["File", "Help", "Settings"], (
        f"the application menu bar exposes {names}; expected exactly "
        f"['File', 'Help', 'Settings']. "
        f"Application controls: {describe(tree.application_controls())}"
    )
    assert all(node.ancestor_roles[:1] == (UIA_MENU_BAR,) for node in items), (
        "every menu must sit directly under a menu bar; "
        f"got {[(n.name, n.ancestor_roles[:1]) for n in items]}"
    )
    assert not any("&" in name for name in names), f"mnemonic markup reached the tree: {names}"


def test_the_title_bar_controls_are_announced(tree: Tree) -> None:
    """The window's own buttons must be reachable by a screen reader too.

    Not this application's code, but it is part of what a user of the application encounters,
    and it costs nothing to notice if a frameless-window change ever removes it.
    """
    buttons = {node.name for node in tree.of_type(UIA_BUTTON)}
    missing = TITLE_BAR_BUTTONS - buttons
    assert not missing, (
        f"title bar buttons {sorted(missing)} missing from the tree; found {sorted(buttons)}"
    )


def test_no_interactive_control_reaches_the_tree_without_a_name(tree: Tree) -> None:
    """`NFR-005`. Over every interactive control, not only the ones this file names.

    A control added later without a label fails here rather than shipping unreadable.

    Scoped to `OPERABLE_TYPES` — the roles a user actually operates. **Check boxes** were added by
    `T-235` and are not a formality: Qt gives a *checkable* `QToolButton` the `CheckBox` role, so
    the queue's own run control was outside this sweep for as long as it has existed. It was
    outside the tree entirely as well, which is the finding that led here.

    **The editing roles were added by `P4EXIT-R1`**, and the shape is the same a third time: the
    tuple listed the roles *this window* has, so Phase 4's own screens — Settings and the add
    dialog, made of edits, combo boxes, spin boxes and tables — were outside a sweep whose
    docstring says *"every interactive control"*. Widening the roles is half; the other half is
    that those screens reach the tree at all, which is what the dialog tests below do.

    Qt and Windows leave the `TitleBar` and the `MenuBar` **container** unnamed, which the first
    CI run of this assertion flagged as two violations. They are not: a screen reader announces
    those by role, and their children carry the names. Requiring a name there would assert something
    the platform does not do, and the only way to make it pass would be to weaken it.
    """
    interactive = tuple(node for node in tree.descendants if node.control_type in OPERABLE_TYPES)
    assert interactive, "no interactive controls in the tree at all"

    unnamed = tuple(node for node in interactive if not node.name.strip())
    assert not unnamed, f"{len(unnamed)} control(s) expose no accessible name: {describe(unnamed)}"


# --- the menus themselves -------------------------------------------------------------------
#
# `T026-R2`: `Quit` and `About` live in popup menus, which on Windows are their own top-level
# windows. Querying only the main window's HWND can never see them, so either action could
# have been deleted or mis-roled with the suite still green. Each menu is opened and its own
# handle queried.


@pytest.mark.parametrize(
    ("menu_title", "expected_items"),
    # Transcribed by hand, not read from the window: this is the statement of what the menus
    # are supposed to publish, and deriving it from `menuBar()` would only prove the menu equals
    # itself. `T-016` added "Add URLs...", and this line is where that had to be declared.
    # **`&Settings` was missing until `T-200`**, and the gap is the shape this file exists to
    # catch. The menu-bar equality above was updated when `T-146` added the menu — it is the
    # assertion that *tripped* on it — while this parametrisation, which is the only thing
    # asserting what is *inside* each menu, was not. So the menu was published and its one action
    # was checked by nothing on the platform where checking it is possible.
    #
    # **`Start` and `Clear finished` joined `&File` in `T-246`**, and this line is the reason that
    # task could not be folded into a focused correction: the two verbs the toolbar draws are the
    # same `QAction`s the menu now holds, and **this is the only assertion on either platform that
    # would notice if one of them stopped being published**. `Start` is the run control's stopped
    # label — the text follows the state, and a freshly built window has never run.
    [
        ("&File", ["Add URLs...", "Start", "Clear finished", "Quit"]),
        ("&Settings", ["Settings..."]),
        ("&Help", ["About"]),
    ],
)
def test_each_menu_publishes_exactly_its_actions(
    window: MainWindow, menu_title: str, expected_items: list[str]
) -> None:
    """Every action a user can trigger must be announced, by name and as a menu item."""
    # `actions` is held for the whole test, not just the lookup loop. The QAction wrappers are
    # what keep the QMenu wrappers alive; releasing them mid-test raises "Internal C++ object
    # (QMenu) already deleted", which is how this failed on its first CI run — the same trap
    # that took three rounds to diagnose in test_windows_desktop.py.
    actions = window.menuBar().actions()
    menus: dict[str, QMenu] = {}
    for action in actions:
        menu = action.menu()
        # isinstance, not `is not None`: PySide6 types `QAction.menu()` as `QObject`.
        if isinstance(menu, QMenu):
            menus[menu.title()] = menu

    menu = menus[menu_title]
    menu.popup(window.mapToGlobal(window.rect().topLeft()))
    QApplication.processEvents()
    try:
        subtree = read_tree(int(menu.winId()))
        names = sorted(node.name for node in subtree.of_type(UIA_MENU_ITEM))
        assert names == sorted(expected_items), (
            f"{menu_title} publishes {names}, expected {sorted(expected_items)}. "
            f"Full subtree: {describe(subtree.descendants)}"
        )
    finally:
        menu.close()
        QApplication.processEvents()


# --- the toolbar (`T-235`) ------------------------------------------------------------------


def test_the_toolbars_three_verbs_are_each_announced(window: MainWindow, tree: Tree) -> None:
    """`NFR-005` over the controls a user reaches first, which this file had never seen.

    **Written out here, not imported and not matched loosely** (`T235-R1`). The same rule the menu
    test follows, and for the same reason: an expected name taken from production moves with
    production, so a rename that silences a verb would rename the assertion too and the test would
    go on passing. The first version of this imported `ADD_URLS_BUTTON` while its docstring claimed
    the names were transcribed — a gate that did not gate what it said it did.

    **The toolbar's buttons are compared as a set, exactly.** A missing verb fails, a fourth verb
    fails, and a re-worded one fails. The title bar's own `Close`/`Minimize`/`Maximize` are the
    frame's rather than this application's — `ElementFromHandle` returns the whole frame — so they
    are excluded by name, which is what `TITLE_BAR_BUTTONS` already exists for.

    **The run control is not here**: it is a `CheckBox`, not a `Button`, and its two states are
    the next test's subject.
    """
    named = {node.name.strip() for node in tree.of_type(UIA_BUTTON) if node.name.strip()}
    ours = named - set(TITLE_BAR_BUTTONS)
    assert ours == {"+ Add URLs", "Clear finished"}, (
        f"the toolbar publishes {sorted(ours)} as buttons, expected "
        f"['+ Add URLs', 'Clear finished']. Full tree: {describe(tree.descendants)}"
    )


def test_the_run_control_is_announced_in_both_of_its_states(window: MainWindow, tree: Tree) -> None:
    """`UX-006`: one checkable control with two labels, so one reading covers half of it.

    It reads `&Start` stopped and `&Stop` running (`T-220`), and its accessible name follows the
    label. A check in one state says nothing about the other — and the running state is the one a
    user is in while they are waiting, which is when they are most likely to be listening.

    **The tree is re-read after the state changes**, because a snapshot taken before it is a
    snapshot of the other state.

    **It is a `CheckBox`, and finding that out is what this test was for.** The first version read
    `UIA_BUTTON` and failed on the Windows runner with
    `Buttons: ['+ Add URLs', 'Clear finished', 'Close', 'Maximize', 'Minimize']` — the run control
    absent from the tree altogether. Qt gives a *checkable* `QToolButton` the accessible role
    `CheckBox` (measured locally: `Role.CheckBox` against `Role.Button` for its two neighbours),
    and UI Automation carries that through. So the queue's main control sat outside a sweep scoped
    to buttons and menu items for as long as both have existed, and the sweep above now includes
    the role.
    """
    run = window.run_action
    assert run is not None

    stopped = {node.name.strip() for node in tree.of_type(UIA_CHECKBOX) if node.name.strip()}
    assert stopped == {"Start"}, (
        f"a stopped queue publishes {sorted(stopped)} as check boxes, expected ['Start']"
    )

    window.show_queue_running(True)
    QApplication.processEvents()
    running = {
        node.name.strip()
        for node in read_tree(int(window.winId())).of_type(UIA_CHECKBOX)
        if node.name.strip()
    }
    assert running == {"Stop"}, (
        f"a running queue publishes {sorted(running)} as check boxes, expected ['Stop']"
    )


# --- Phase 4's own screens (`P4EXIT-R1`) ----------------------------------------------------
#
# **Every test below takes `composed`, not `window`.** The first version took `window`, which is
# `MainWindow(geometry_file=..., control_bar=True)` and nothing else — no writers, no output
# directory, no manager, no jobs. `open_settings()` returns `None` on such a window and
# `open_add_dialog()` raises, so all three tests failed or errored **before `read_tree` was ever
# called**: three pre-query failures, zero UIA calls, as the reviewer measured by running these
# exact bodies on Linux with the platform boundary stubbed. A test that cannot open its screen
# cannot audit it, and this one would have reported the fixture's gap as an accessibility defect.
#
# `composed` is `tests/ui/conftest.py`'s, and it is the application wired by `app.compose` with
# an orderly `shutdown.begin()` teardown. It is the same fixture fourteen Linux cases already
# drive, including `every_surface`, which asserts `open_settings()` is not `None` — so the routes
# these tests depend on have a standing check on the platform that can run one.
#
# `window` stays for the tests above it: they are about the main window's own furniture, they
# have passed on Windows in that form, and swapping a fixture under checks I cannot execute would
# be changing evidence I cannot re-take.


def _values_on_display(screen: QWidget) -> frozenset[str]:
    """What every combo box on `screen` is **currently showing**, read from the live widgets.

    This is the positive control the purpose check needs (`P4EXIT-R1`). The superseded version
    compared a combo's name against every `ListItem` name in the published tree, required none to
    exist, and associated none with a particular combo — so a tree holding one combo named
    `Best video available` and no list items passed it. Asking Qt what the controls actually
    display cannot be empty by accident, and the assertion says so out loud if it is.
    """
    return frozenset(
        combo.currentText() for combo in screen.findChildren(QComboBox) if combo.isVisibleTo(screen)
    )


def test_the_settings_screen_is_published_with_named_controls(composed: MainWindow) -> None:
    """**`P4EXIT-R1`.** Settings was never queried through UI Automation.

    The existing Settings test opens the **menu** and asserts the menu item — it never opens the
    dialog, so the whole of `REQ-023`'s screen, which Phase 4 exists to have built, was outside
    the published tree this phase's criterion 2 is about. Its controls are edits, combo boxes,
    spin boxes and buttons: four roles, none of which the sweep covered either.

    **Asserted on the dialog's own `HWND`**, not the main window's, for the reason
    `test_the_about_dialog…` records: a modal is its own top-level window, and reading the parent
    would find none of it.
    """
    settings = composed.open_settings()
    assert settings is not None, (
        "composition wired no settings writers, so the Settings screen never opened and the "
        "sweep below would cover nothing"
    )
    QApplication.processEvents()
    try:
        subtree = read_tree(int(settings.winId()))
        operable = assert_every_control_is_named(subtree, "Settings screen")

        # **The editing roles are actually present**, or this passed on the button box alone —
        # which is the vacuity `P4EXIT-R1` found one screen over.
        kinds = {node.control_type for node in operable}
        assert kinds & {UIA_EDIT, UIA_COMBOBOX, UIA_SPINNER}, (
            "Settings published no edit, combo box or spin box to UI Automation, so its actual "
            f"controls are not in this sweep. Found: {describe(operable)}"
        )
    finally:
        settings.close()
        QApplication.processEvents()


def test_the_add_dialog_is_published_with_named_controls(composed: MainWindow) -> None:
    """**`P4EXIT-R1`.** The add dialog was never queried through UI Automation either.

    It is the screen a user meets first and the one Phase 4 reshaped most — the URL box, the
    staging list, the batch preset control and the button box. None of it reached the tree these
    tests assert on.

    **What this does not do is drive a probe.** Reaching the staging *pages* needs a resolved row,
    and a failure there would be ambiguous with a probe failure — the bound `Surface`'s own
    `opened_through_its_route` records. The sweep below covers those pages as constructed
    screens, on this platform, which is the half `P4EXIT-R1` found delegated to Linux.
    """
    add = composed.open_add_dialog()
    QApplication.processEvents()
    try:
        subtree = read_tree(int(add.winId()))
        operable = assert_every_control_is_named(subtree, "add dialog")

        kinds = {node.control_type for node in operable}
        assert UIA_EDIT in kinds, (
            "the add dialog published no edit control, so the URL box a user types into is not "
            f"in this sweep. Found: {describe(operable)}"
        )
    finally:
        add.close()
        QApplication.processEvents()


def test_a_combo_box_announces_its_purpose_not_its_current_value(composed: MainWindow) -> None:
    """**`P4EXIT-R1`.** A control named for its value tells a screen reader nothing about itself.

    The assertion is `uia_contract.assert_combos_announce_their_purpose`, and
    `tests/ui/test_uia_contract.py` proves on *this* platform that it rejects both a combo with no
    name and a combo named for what it holds — including the reviewer's own counterexample, a
    tree carrying a combo named `Best video available` and no list item at all, which the
    superseded version passed.

    What this test contributes is the real screen: Settings as composed, and the values its combo
    boxes are actually displaying, read from the widgets themselves.
    """
    settings = composed.open_settings()
    assert settings is not None, (
        "composition wired no settings writers, so the Settings screen never opened"
    )
    QApplication.processEvents()
    try:
        subtree = read_tree(int(settings.winId()))
        assert_combos_announce_their_purpose(
            subtree, "Settings screen", displayed_values=_values_on_display(settings)
        )
    finally:
        settings.close()
        QApplication.processEvents()


def test_every_surface_this_application_shows_is_published_with_named_controls(
    every_surface: list[Surface], qapp: QApplication
) -> None:
    """**`P4EXIT-R1`.** The published tree of every screen, not only the two opened above.

    Options, `PresetManager`, the queue's `FormatDialog` and the three editing panels had **no
    Windows published-tree query at all**, and the comment this replaces said so — it pointed at
    the Linux audit as their coverage. The amended criterion asks for both platforms, and a Qt
    accessible name reaching AT-SPI is not evidence that the same name reaches UI Automation:
    `T200-R7` is the standing proof that the two bridges disagree about combo boxes specifically.

    **The inventory is `every_surface`**, which is the one the Linux audits walk. A second list
    would drift, and `T238-R5` records what that drift costs — a reader calling an omission a
    deliberate scope. Four of the thirteen are opened through their real routes; the rest are
    constructed, which `Surface.opened_through_its_route` records and which is a bound rather
    than a preference.

    **The floor is derived, not listed** (`T-227`). `Surface.expects_a_tab_chain` already records
    which screens have controls a keyboard reaches — the main window is the one deliberate `False`
    (`T-234`: nothing on its toolbar may take focus), and the Linux tab sweep holds every other
    surface to it. So the floor is *"a screen the inventory says has a tab chain must publish an
    operable control here too"*, which needs no hand-kept table and cannot be satisfied by a
    screen that failed to realise.
    """
    with_a_floor = [surface.label for surface in every_surface if surface.expects_a_tab_chain]
    assert with_a_floor, (
        "the inventory declares no surface with a tab chain, so every floor below is skipped and "
        "this sweep passes by looking at nothing"
    )

    for surface in every_surface:
        surface.widget.show()
        surface.widget.raise_()
        qapp.processEvents()
        subtree = read_tree(int(surface.widget.winId()))

        published = named_operable(subtree)
        unnamed = tuple(node for node in published if not node.name.strip())
        assert not unnamed, (
            f"{len(unnamed)} control(s) on the {surface.label} expose no accessible name to "
            f"Narrator: {describe(unnamed)}"
        )
        if not surface.expects_a_tab_chain:
            continue
        assert focusable(surface.widget), (
            f"the {surface.label} declares a tab chain and Qt reports no Tab-reachable widget on "
            "it, so it did not realise and the floor below would pass over nothing"
        )
        assert published, (
            f"the {surface.label} has Tab-reachable widgets in Qt and publishes no operable "
            "control to UI Automation, so a screen reader user meets a window with nothing in "
            f"it. Full subtree: {describe(subtree.descendants)}"
        )


def test_the_about_dialog_and_its_close_button_are_announced(window: MainWindow) -> None:
    """`T026-R2`: the About box was never opened, so its Close control sat outside the tree.

    A dialog a screen reader cannot name, containing a button it cannot name, is unusable —
    and it is the one modal surface the application currently has.

    **The dialog's own Close button, not the title bar's.** Both are `Button` role and both are
    named "Close", so a name-and-role match alone is satisfied by the window furniture — the
    reviewer's harness passed this check with the title-bar Close as the only button present.
    The `QMessageBox` button lives outside the title bar's subtree, and that is what is
    asserted.
    """
    about = window.show_about()
    QApplication.processEvents()
    try:
        subtree = read_tree(int(about.winId()))

        assert subtree.window.name == "About", (
            f"the About dialog is announced as {subtree.window.name!r}"
        )
        assert subtree.window.control_type == UIA_WINDOW

        content_buttons = [
            node.name for node in subtree.application_controls() if node.control_type == UIA_BUTTON
        ]
        assert any("close" in name.lower() for name in content_buttons), (
            "the About dialog exposes no Close button of its own to Narrator — the title "
            f"bar's Close does not count. Content buttons: {content_buttons}. "
            f"Full subtree: {describe(subtree.descendants)}"
        )
    finally:
        about.close()
        QApplication.processEvents()
