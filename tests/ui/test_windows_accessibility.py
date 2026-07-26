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

What this does **not** claim: that Narrator's announcements are *coherent*. A correct tree is
necessary and not sufficient, and the difference stays a human judgement (`ai/TESTING.md` §9).
"""

import ctypes
import sys
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from tracks_and_trails.ui.main_window import APP_NAME, MainWindow

pytestmark = pytest.mark.windows_desktop

if sys.platform != "win32":
    pytest.skip("UI Automation is a Windows API", allow_module_level=True)

# Imported plainly, never via `importorskip`. On Windows comtypes is a declared dev dependency,
# so a failure to import is a broken environment, not a reason to opt out — and a skip here
# would delete the only automated accessibility gate while leaving the job green.
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


@pytest.fixture(scope="module")
def automation() -> Any:
    """The UI Automation client object.

    Fails rather than skips if it cannot be created. A skip here would quietly remove the only
    check standing between `ai/TESTING.md` §9's manual accessibility item and its retirement.
    """
    comtypes.client.GetModule("UIAutomationCore.dll")
    from comtypes.gen import UIAutomationClient

    return comtypes.client.CreateObject(CUIAUTOMATION, interface=UIAutomationClient.IUIAutomation)


@pytest.fixture
def window_element(automation: Any, qapp: QApplication, tmp_path: Path) -> Any:
    """The main window as UI Automation sees it."""
    window = MainWindow(geometry_file=tmp_path / "window.toml")
    window.show()
    window.raise_()
    window.activateWindow()
    QApplication.processEvents()

    element = automation.ElementFromHandle(ctypes.c_void_p(int(window.winId())))
    assert element is not None, "UI Automation cannot see the window at all"
    return element


def _descendants(automation: Any, element: Any) -> list[Any]:
    found = element.FindAll(TREE_DESCENDANTS, automation.CreateTrueCondition())
    return [found.GetElement(index) for index in range(found.Length)]


def test_the_window_is_published_with_its_name_and_role(window_element: Any) -> None:
    """The top-level element is what a screen reader announces on focus."""
    assert window_element.CurrentName == APP_NAME, (
        f"UI Automation announces the window as {window_element.CurrentName!r}"
    )
    assert window_element.CurrentControlType == UIA_WINDOW


def test_the_menu_bar_reaches_the_accessibility_tree(automation: Any, window_element: Any) -> None:
    """A menu bar absent from the tree is a menu bar Narrator cannot reach."""
    types = [element.CurrentControlType for element in _descendants(automation, window_element)]
    assert UIA_MENU_BAR in types, (
        f"no menu bar in the UI Automation tree; found control types {sorted(set(types))}"
    )


def test_every_menu_item_has_a_non_empty_accessible_name(
    automation: Any, window_element: Any
) -> None:
    """`NFR-005`'s actual requirement, asserted against what Windows publishes.

    Iterates whatever the tree contains rather than a fixed list, so a control added later
    without a label fails here instead of shipping silently unreadable.
    """
    items = [
        element
        for element in _descendants(automation, window_element)
        if element.CurrentControlType == UIA_MENU_ITEM
    ]
    assert items, "no menu items in the UI Automation tree — the File and Help menus should be"

    unnamed = [item for item in items if not (item.CurrentName or "").strip()]
    assert not unnamed, f"{len(unnamed)} menu item(s) expose no accessible name to Narrator"


def test_the_file_and_help_menus_are_announced_without_mnemonic_markup(
    automation: Any, window_element: Any
) -> None:
    """Mnemonics are markup for the eye; a screen reader must not read the ampersand.

    Qt strips `&` when publishing to the platform accessibility bridge. Asserting it catches a
    regression where the raw title reaches the tree and Narrator says "ampersand File".
    """
    names = {
        (element.CurrentName or "")
        for element in _descendants(automation, window_element)
        if element.CurrentControlType == UIA_MENU_ITEM
    }
    assert not any("&" in name for name in names), f"mnemonic markup reached the tree: {names}"
    assert {"File", "Help"} <= names, f"expected File and Help menus, tree exposes {names}"
