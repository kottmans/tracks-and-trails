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
from PySide6.QtWidgets import QApplication

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

#: `CLSID_CUIAutomation`.
CUIAUTOMATION = "{ff48dba4-60ef-4201-aa87-54103eef594e}"

#: `TreeScope_Descendants`.
TREE_DESCENDANTS = 4

#: Generous: the tree is tiny, but a first call has to build Qt's accessibility bridge and
#: generate the comtypes typelib wrapper. A timeout here fails the test rather than hanging CI.
QUERY_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class Node:
    """One accessibility element, reduced to the data a screen reader would use."""

    name: str
    control_type: int


@dataclass(frozen=True)
class Tree:
    """A window and everything beneath it, as UI Automation publishes it."""

    window: Node
    descendants: tuple[Node, ...]

    def of_type(self, control_type: int) -> tuple[Node, ...]:
        return tuple(node for node in self.descendants if node.control_type == control_type)


def _read_tree(hwnd: int) -> Tree:
    """Snapshot the UI Automation tree for `hwnd`. Runs on the calling (worker) thread."""
    # COINIT_MULTITHREADED. A UIA client belongs in the MTA; an STA worker would reintroduce
    # the message-pump dependency this thread exists to escape.
    ctypes.windll.ole32.CoInitializeEx(None, 0)
    try:
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient

        automation = comtypes.client.CreateObject(
            CUIAUTOMATION, interface=UIAutomationClient.IUIAutomation
        )
        element = automation.ElementFromHandle(ctypes.c_void_p(hwnd))
        if element is None:
            raise AssertionError("UI Automation cannot see the window at all")

        found = element.FindAll(TREE_DESCENDANTS, automation.CreateTrueCondition())
        descendants = tuple(
            Node(
                name=found.GetElement(index).CurrentName or "",
                control_type=found.GetElement(index).CurrentControlType,
            )
            for index in range(found.Length)
        )
        return Tree(
            window=Node(name=element.CurrentName or "", control_type=element.CurrentControlType),
            descendants=descendants,
        )
    finally:
        ctypes.windll.ole32.CoUninitialize()


@pytest.fixture
def tree(qapp: QApplication, tmp_path: Path) -> Tree:
    """The live window's accessibility tree, read without blocking the GUI thread.

    The main thread keeps pumping Qt events for the duration, because that is what answers the
    `WM_GETOBJECT` the UIA client sends. Stop pumping and the query returns an empty tree.
    """
    window = MainWindow(geometry_file=tmp_path / "window.toml")
    window.show()
    window.raise_()
    window.activateWindow()
    QApplication.processEvents()
    hwnd = int(window.winId())

    result: dict[str, object] = {}

    def worker() -> None:
        try:
            result["tree"] = _read_tree(hwnd)
        except BaseException as error:
            # Caught broadly and re-raised on the main thread below. An exception escaping a
            # worker thread would otherwise be printed and discarded, leaving the fixture to
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


def test_the_window_is_published_with_its_name_and_role(tree: Tree) -> None:
    """The top-level element is what a screen reader announces on focus."""
    assert tree.window.name == APP_NAME, (
        f"UI Automation announces the window as {tree.window.name!r}"
    )
    assert tree.window.control_type == UIA_WINDOW


def test_the_menu_bar_reaches_the_accessibility_tree(tree: Tree) -> None:
    """A menu bar absent from the tree is a menu bar Narrator cannot reach."""
    assert tree.of_type(UIA_MENU_BAR), (
        "no menu bar in the UI Automation tree; found control types "
        f"{sorted({node.control_type for node in tree.descendants})}"
    )


def test_every_menu_item_has_a_non_empty_accessible_name(tree: Tree) -> None:
    """`NFR-005`'s actual requirement, asserted against what Windows publishes.

    Iterates whatever the tree contains rather than a fixed list, so a control added later
    without a label fails here instead of shipping silently unreadable.
    """
    items = tree.of_type(UIA_MENU_ITEM)
    assert items, "no menu items in the UI Automation tree — File and Help should both be"

    unnamed = [item for item in items if not item.name.strip()]
    assert not unnamed, f"{len(unnamed)} menu item(s) expose no accessible name to Narrator"


def test_the_file_and_help_menus_are_announced_without_mnemonic_markup(tree: Tree) -> None:
    """Mnemonics are markup for the eye; a screen reader must not read the ampersand.

    Qt strips `&` when publishing to the platform accessibility bridge. Asserting it catches a
    regression where the raw title reaches the tree and Narrator says "ampersand File".
    """
    names = {node.name for node in tree.of_type(UIA_MENU_ITEM)}
    assert not any("&" in name for name in names), f"mnemonic markup reached the tree: {names}"
    assert {"File", "Help"} <= names, f"expected File and Help menus, tree exposes {names}"
