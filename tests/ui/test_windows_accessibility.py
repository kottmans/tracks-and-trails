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
necessary and not sufficient, and the difference stays a human judgement (`ai/TESTING.md` §9).
"""

import ctypes
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMenu

from tracks_and_trails.ui.main_window import APP_NAME, MainWindow

pytestmark = pytest.mark.windows_desktop

if sys.platform != "win32":
    pytest.skip("UI Automation is a Windows API", allow_module_level=True)

# Imported plainly, never via `importorskip`. On Windows comtypes is a declared dev dependency,
# so a failure to import is a broken environment, not a reason to opt out — and a skip here
# would delete the only automated accessibility gate while leaving the job green.
import comtypes  # noqa: E402
import comtypes.client  # noqa: E402

#: UI Automation control type IDs (`UIAutomationCore.h`). Spelled out rather than imported,
#: because the generated comtypes module names them inconsistently across versions.
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

#: Role names, for failure messages that a reader can interpret without a lookup table.
ROLE_NAMES = {
    UIA_WINDOW: "Window",
    UIA_MENU_BAR: "MenuBar",
    UIA_MENU_ITEM: "MenuItem",
    UIA_BUTTON: "Button",
    UIA_CHECKBOX: "CheckBox",
    UIA_TITLE_BAR: "TitleBar",
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

#: `CLSID_CUIAutomation`.
CUIAUTOMATION = "{ff48dba4-60ef-4201-aa87-54103eef594e}"

#: Fails a malformed or cyclic tree instead of recursing until CI times out.
MAX_TREE_DEPTH = 32

#: Generous: the tree is tiny, but a first call has to build Qt's accessibility bridge and
#: generate the comtypes typelib wrapper. A timeout here fails the test rather than hanging CI.
QUERY_TIMEOUT_SECONDS = 30.0


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

    @property
    def is_title_bar_furniture(self) -> bool:
        """Whether Windows contributed this, rather than the application."""
        return UIA_TITLE_BAR in self.ancestor_roles


@dataclass(frozen=True)
class Tree:
    """A window and everything beneath it, as UI Automation publishes it."""

    window: Node
    descendants: tuple[Node, ...]

    def of_type(self, control_type: int) -> tuple[Node, ...]:
        return tuple(node for node in self.descendants if node.control_type == control_type)

    def application_controls(self) -> tuple[Node, ...]:
        """Everything the application owns — the tree minus the native title bar's subtree.

        Every assertion about *this project's* accessibility goes through here. Asserting over
        `descendants` lets Windows' own controls satisfy the contract, which is exactly how the
        previous version could pass with no `File` or `Help` at all.
        """
        return tuple(node for node in self.descendants if not node.is_title_bar_furniture)


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


def describe(nodes: tuple[Node, ...]) -> list[str]:
    """Render a tree for a failure message: what Narrator would actually encounter."""
    return [f"{ROLE_NAMES.get(n.control_type, n.control_type)}:{n.name!r}" for n in nodes]


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

    Scoped to menu items, buttons and **check boxes** — the roles a user actually operates. The
    third was added by `T-235` and is not a formality: Qt gives a *checkable* `QToolButton` the
    `CheckBox` role, so the queue's own run control was outside this sweep for as long as it has
    existed. It was outside the tree entirely as well, which is the finding that led here.

    Qt and Windows leave the `TitleBar` and the `MenuBar` **container** unnamed, which the first
    CI run of this assertion flagged as two violations. They are not: a screen reader announces
    those by role, and their children carry the names. Requiring a name there would assert something
    the platform does not do, and the only way to make it pass would be to weaken it.
    """
    interactive = tuple(
        node
        for node in tree.descendants
        if node.control_type in (UIA_MENU_ITEM, UIA_BUTTON, UIA_CHECKBOX)
    )
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
    [("&File", ["Add URLs...", "Quit"]), ("&Help", [f"About {APP_NAME}"])],
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


# --- the About dialog -----------------------------------------------------------------------


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

        assert subtree.window.name == f"About {APP_NAME}", (
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
