"""The accessibility pass: names, roles, keyboard reachability and focus order (`T-200`).

`NFR-005` has been argued **surface by surface** for the whole project — `T105-R3` established
that it asks for reachability rather than a particular arrangement, `T118-R5` that a context menu
is not authority to drop a visible control, `UX-007` ruled the preset manager's layout and the
template preview's tab stop. Every one of those is a local judgement about one screen. **This file
asks the global question**: can a user who never touches the mouse do everything the application
does, and is every control they land on announced?

## What this file checks, and what it deliberately does not

This asserts the tree **Qt will publish** — `QAccessible`, in process. That is not the same claim
as *"a screen reader announced it"*, and `tests/ui/test_windows_accessibility.py` makes the
distinction the other way round for its own platform: it queries **UI Automation** precisely
because asserting `QAccessible` there *"would be Qt reporting on Qt"*.

The distinction is real and neither file replaces the other:

- **The source tree** — names, roles, focus. Checked **here**, on every platform: it is what every
  bridge publishes *from*, and it is the half a defect actually lives in.
- **The published tree.** `test_windows_accessibility.py`, Windows only — the bridge can be wrong
  independently, and Windows is where this project can query the real one.
- **Whether the announcement is *coherent*.** Nowhere automated (`OPS-004`). Subjective; Orca on
  Linux and the pre-release Narrator session own it.

**On Linux there is no equivalent of the UI Automation query.** Reading the published tree needs
AT-SPI, which needs a real display and a running assistive client; the suite runs offscreen on
`QT_QPA_PLATFORM=offscreen` by `tests/ui/conftest.py`, where no bridge activates —
`QAccessible.isActive()` is `False` and stays so. So the source tree is what is automatable here,
and the Orca half is recorded as a human check in `T-200`'s entry rather than pretended at.

## Driven through the routes a user takes

Each surface is opened the way the application opens it — `open_add_dialog()`, `open_settings()`,
`show_about()` — rather than constructed directly. **`T-201` is why.** Its text was written, tested
and correct for twelve error classes and reached nobody, because the only widget that composed it
was one `UX-005` §2 had left nothing constructing. A pass that instantiates a screen in order to
audit it can pass over a screen no user can open, which is the same defect wearing this file's
clothes.

The surfaces below the add dialog — the format table, the template editor, the options dialog, the
preset manager — are reached through a row's own controls and are constructed here, with that
difference stated at each one rather than blurred.
"""

import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

import pytest
from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QAccessible, QAccessibleInterface, QAction
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLineEdit,
    QMenu,
    QScrollArea,
    QToolBar,
    QWidget,
    QWidgetAction,
)

from tracks_and_trails import app as application
from tracks_and_trails.ui.keyboard import ROUTE_ELSEWHERE_PROPERTY
from tracks_and_trails.ui.main_window import MainWindow

#: The roles a user **operates**, and therefore the ones that must carry a name.
#:
#: Transcribed from `tests/ui/test_windows_accessibility.py`'s own scope — menu items, buttons and
#: check boxes — and widened to the roles this application's screens actually use. **The check box
#: is not a formality**: Qt gives a *checkable* `QToolButton` the `CheckBox` role, so the queue's
#: run control sat outside that file's sweep for as long as it existed (`T-235`).
#:
#: Containers are absent on purpose. Qt leaves a menu bar, a tool bar's own frame and a plain
#: `Client` unnamed, a screen reader announces them by role, and their children carry the names —
#: requiring a name there would assert something the platform does not do, and the only way to
#: make it pass would be to weaken it. That is the Windows file's finding, restated because this
#: sweep would otherwise rediscover it as a dozen failures.
OPERABLE_ROLES: Final = frozenset(
    {
        QAccessible.Role.Button,
        QAccessible.Role.CheckBox,
        QAccessible.Role.ComboBox,
        QAccessible.Role.EditableText,
        QAccessible.Role.MenuItem,
        QAccessible.Role.RadioButton,
        QAccessible.Role.SpinBox,
        QAccessible.Role.Slider,
        QAccessible.Role.PageTab,
    }
)

#: Containers a screen reader announces **by name**, and which therefore need one (`T200-R3`).
#:
#: A table, a list and a tree are not operated by pressing them, so they are not in
#: `OPERABLE_ROLES` — and that is precisely how the format table came to be swept without being
#: checked. Deleting its accessible name left every test green: the name lives on the `Table` node,
#: every role beneath it is a `Cell`, and nothing was looking at either.
#:
#: These are the surfaces a user arrows *into*, and *"Available formats"* or *"Download queue"* is
#: what tells them where they have landed. An unnamed one is announced as "table".
NAMED_CONTAINERS: Final = frozenset(
    {QAccessible.Role.Table, QAccessible.Role.List, QAccessible.Role.Tree}
)

#: Qt's own furniture, which Qt names and this project does not own.
#:
#: `qt_toolbar_ext_button` is the `»` overflow a `QToolBar` grows when it runs out of room. It is
#: Qt's widget, created and destroyed by Qt, and it carries no accessible name in any application.
#: **Named here rather than skipped silently**, because "the platform leaves this unnamed" and "we
#: forgot to label this" are different facts and a sweep that cannot tell them apart is a sweep
#: nobody will trust the next time it goes red.
PLATFORM_FURNITURE: Final = frozenset(
    {
        "qt_toolbar_ext_button",
        "qt_menubar_ext_button",
        # A `QTableView`'s select-all corner, between the two headers. Qt builds it, Qt leaves it
        # unnamed and mouse-only, and the rows and columns it selects are reachable through the
        # table itself — which is the table's own keyboard contract, not one this project sets.
        "qt_tableview_cornerbutton",
    }
)


def is_platform_furniture(node: Node) -> bool:
    """Whether a node is a widget **Qt** creates and names, rather than one this project owns.

    Two shapes, both found by this sweep rather than assumed:

    - The named ones, in `PLATFORM_FURNITURE` — a toolbar's `»` overflow and its menu-bar twin.
    - **Widgets Qt builds inside another control**, which have no object name to list: a
      `QLineEdit`'s clear button, and the `QListView` a `QComboBox` drops down. Qt creates,
      names and destroys both. Matched by their parent, because there is nothing else to match on.

    Naming these rather than skipping them silently is the point: *"the platform leaves this
    unnamed"* and *"we forgot to label this"* are different facts, and a sweep that cannot tell
    them apart is one nobody will trust the next time it goes red.
    """
    return node.object_name in PLATFORM_FURNITURE or node.inside_a_control


@dataclass(frozen=True, slots=True)
class Node:
    """One node of the accessible tree, flattened for assertion and for a readable failure."""

    depth: int
    role: QAccessible.Role
    name: str
    kind: str
    object_name: str
    #: Whether this node is a widget Qt builds inside another control — see
    #: `is_platform_furniture`. A `QLineEdit`'s clear button and a `QComboBox`'s dropdown view are
    #: both of these, and neither has an object name to recognise it by.
    inside_a_control: bool = False

    def __str__(self) -> str:
        role = str(self.role).rsplit(".", maxsplit=1)[-1]
        return f"{'  ' * self.depth}{role} {self.name!r} <{self.kind} {self.object_name}>"


def _is_built_by_a_control(widget: QWidget) -> bool:
    """Whether Qt built `widget` inside another control, rather than this project placing it."""
    parent = widget.parentWidget()
    if isinstance(parent, QLineEdit | QComboBox):
        return True
    # A combo's popup sits in a frame of its own, one level further out.
    grandparent = parent.parentWidget() if parent is not None else None
    return isinstance(grandparent, QComboBox)


def walk(interface: QAccessibleInterface | None, depth: int = 0) -> list[Node]:
    """Every node under `interface`, depth first, in the order a bridge would publish them."""
    if interface is None or not interface.isValid():
        return []
    # Qt's stubs type these as never-`None` and the runtime disagrees — a node can be published
    # for an object Qt has already released. The same mismatch `row_delegate._paint` documents for
    # `option.widget`, and stated the same way: a `cast` says what the contract really is, where a
    # `type: ignore` would only silence the check that noticed.
    obj = cast("QObject | None", interface.object())
    nodes = [
        Node(
            depth=depth,
            role=interface.role(),
            name=interface.text(QAccessible.Text.Name),
            kind=type(obj).__name__ if obj is not None else "",
            object_name=obj.objectName() if isinstance(obj, QWidget) else "",
            inside_a_control=isinstance(obj, QWidget) and _is_built_by_a_control(obj),
        )
    ]
    for index in range(interface.childCount()):
        nodes.extend(walk(interface.child(index), depth + 1))
    return nodes


def node_for(widget: QWidget, interface: QAccessibleInterface) -> Node:
    """A `Node` for one widget, so `is_platform_furniture` can be asked about it directly."""
    return Node(
        depth=0,
        role=interface.role(),
        name=interface.text(QAccessible.Text.Name),
        kind=type(widget).__name__,
        object_name=widget.objectName(),
        inside_a_control=_is_built_by_a_control(widget),
    )


def tree_of(widget: QWidget) -> list[Node]:
    """The accessible tree for one surface."""
    nodes = walk(QAccessible.queryAccessibleInterface(widget))
    assert nodes, f"{type(widget).__name__} publishes no accessible tree at all"
    return nodes


def is_a_name(text: str) -> bool:
    """Whether `text` is a name a screen reader can read out as a control's purpose.

    **Non-empty is not the test, and finding that out cost a surviving mutation.** Qt falls back to
    a widget's own `text()` when no accessible name is set, so deleting the explicit name from the
    concurrency steppers left them reporting `▲` — non-empty, and announced as "up pointing
    triangle". A sweep that only asked *is it blank* called that named.

    So a name has to contain a **word**. One letter is not one: `+` and `▲` are the shapes this is
    aimed at, and the labels this application actually sets — *"Increase the number of downloads"* —
    clear it easily.
    """
    return any(part.isalpha() for part in text) and len(text.strip()) > 1


def describe(nodes: list[Node]) -> str:
    return "\n".join(str(node) for node in nodes)


def reaches_by_tab(widget: QWidget) -> bool:
    """Whether a keyboard can put focus on `widget` **with Tab** (`T200-R2`).

    **The capability, not the absence of its opposite.** This asked `focusPolicy() != NoFocus`,
    and `Qt.FocusPolicy.ClickFocus` satisfies that while being exactly as mouse-only as `NoFocus`
    is — so setting a control to `ClickFocus` removed it from the keyboard and left every
    accessibility test green. `NoFocus` is 0 and `ClickFocus` is 2; neither carries the `TabFocus`
    bit, which is what the chain walks.

    Testing the bit rather than naming the three policies that happen to include it means a policy
    this project has not used yet is classified by what it *does*.
    """
    return bool(int(widget.focusPolicy()) & int(Qt.FocusPolicy.TabFocus))


def focusable(widget: QWidget) -> list[QWidget]:
    """Every visible descendant **Tab** can land on, the widget itself included.

    `isVisibleTo` rather than `isVisible`, because a surface under test is realised but not
    necessarily shown on the offscreen platform, and a control hidden inside a collapsed box is
    genuinely unreachable while a control on an unshown window is not.

    **Scoped to the surface's own top-level window, which is not a detail.** A dialog opened from
    the main window is *parented* to it, so `findChildren` reaches straight into the Settings
    screen and the add dialog and reports their controls as the window's own. The first run of the
    sweep below did exactly that: it named 39 controls the window's focus chain "never reached",
    every one of them belonging to a different window that has a chain of its own. A focus chain
    does not cross a window boundary, so neither does this.
    """
    home = widget.window()
    found = [
        child
        for child in widget.findChildren(QWidget)
        if reaches_by_tab(child) and child.isVisibleTo(widget) and child.window() is home
    ]
    if reaches_by_tab(widget):
        found.insert(0, widget)
    return found


# --- the surfaces, opened the way the application opens them ----------------------------------


@pytest.fixture
def composed(qapp: QApplication, tmp_path: Path) -> Iterator[MainWindow]:
    """The real application, wired by `app.compose`, so every route below is the real route."""
    composition = application.compose(
        qapp,
        database=tmp_path / "queue.sqlite3",
        output_directory=tmp_path / "downloads",
        geometry_file=tmp_path / "window.toml",
        settings_file=tmp_path / "settings.toml",
        cache_directory=tmp_path / "cache",
        # Nothing is downloaded: every claim here is about widgets.
        entry_point=lambda *_args, **_kwargs: None,
    )
    window = composition.window
    window.show()
    qapp.processEvents()
    yield window
    # **Torn down through the lifecycle composition owns** (`T200-R6`). Closing the window alone
    # left the real `YtdlpService` and the queue writer running, and the file's teardown ran past a
    # twelve-second bound — a sweep of widgets holding a version service open. `shutdown.begin()`
    # is the same route `tests/integration/test_composition.py` drives and the one the application
    # takes when a user closes the window.
    window.close()
    composition.shutdown.begin()
    deadline = time.monotonic() + 30
    while not composition.shutdown.finished and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    qapp.processEvents()
    assert composition.shutdown.finished, "composition never finished shutting down"


def test_the_window_publishes_a_named_role_for_every_control_a_user_operates(
    composed: MainWindow,
) -> None:
    """`NFR-005`, over the whole tree rather than a list of widgets (`T-200`).

    **A per-widget list is a list that drifts** — the criterion says so in as many words, and this
    project has the receipts: `T-235` found the queue's run control had never been in the Windows
    sweep at all, because that sweep enumerated roles and the control had a role nobody had thought
    of. So this walks what Qt publishes and holds every operable node to the same rule.
    """
    nodes = tree_of(composed)
    operable = [node for node in nodes if node.role in OPERABLE_ROLES | NAMED_CONTAINERS]
    assert operable, f"the window publishes no operable control at all:\n{describe(nodes)}"

    unnamed = [
        node for node in operable if not is_a_name(node.name) and not is_platform_furniture(node)
    ]
    assert not unnamed, (
        f"{len(unnamed)} control(s) reach the tree with no accessible name:\n{describe(unnamed)}"
    )


def test_no_control_is_published_without_a_role(composed: MainWindow) -> None:
    """A name with no role is announced as *"Start"* and nothing else — a word, not a control.

    `QAccessible.Role.NoRole` is the value Qt uses when it has nothing to say, so a named node
    carrying it is a control the bridge cannot classify.
    """
    named = [node for node in tree_of(composed) if node.name.strip()]
    roleless = [node for node in named if node.role == QAccessible.Role.NoRole]
    assert not roleless, f"named control(s) published with no role:\n{describe(roleless)}"


def test_every_focusable_control_in_the_window_is_named(composed: MainWindow) -> None:
    """The same rule from the widget side, which catches what the tree flattens.

    A `QAccessible` tree is not one node per widget: Qt merges, promotes and hides. A control can
    therefore be focusable — a user tabs to it, and a screen reader is asked to say what it is —
    while contributing no operable node for the sweep above to inspect.

    **The main window legitimately has almost nothing focusable**, and that is `T-234`'s criterion
    rather than a gap: nothing on its toolbar may take focus, because `T203-R3` recorded a focusable
    toolbar widget stealing `Shift+F10` from the row menu on a freshly opened window. Its verbs are
    reached by menu and by shortcut instead — asserted separately, below. So this sweeps whatever is
    focusable without requiring that anything is.
    """
    unnamed = []
    for widget in focusable(composed):
        if widget.objectName() in PLATFORM_FURNITURE:
            continue
        interface = cast(
            "QAccessibleInterface | None", QAccessible.queryAccessibleInterface(widget)
        )
        # A container that merely accepts focus so its children can be reached announces itself by
        # role; the rule is about controls, and `OPERABLE_ROLES` is where that line is drawn.
        if interface is None or interface.role() not in OPERABLE_ROLES:
            continue
        # **Asked of the interface, not of the widget** — `widget.accessibleName()` is the wrong
        # object for half these controls. A `QToolBar` builds its buttons from `QAction`s and the
        # *action* carries the text, so `Start` and `Clear finished` have an empty
        # `accessibleName()` and a perfectly good published name. Asserting the widget's own field
        # would have demanded a second copy of a name that is already right, which is how a rule
        # ends up making an application worse to satisfy it.
        if not is_a_name(interface.text(QAccessible.Text.Name)):
            unnamed.append(widget)

    assert not unnamed, (
        "focusable control(s) with no accessible name: "
        f"{[(type(w).__name__, w.objectName()) for w in unnamed]}"
    )


# --- keyboard reachability (T-200 criterion 1) ------------------------------------------------


def tab_order(surface: QWidget, qapp: QApplication) -> list[QWidget]:
    """The widgets Tab actually visits, in order, starting from the surface's first focus.

    **Walked through Qt's own `nextInFocusChain` filtering rather than by sending key events.**
    A synthetic `Tab` on the offscreen platform is delivered to whatever holds focus and can be
    swallowed by a widget that handles it itself — a `QTableView` moves between cells — so a
    key-driven walk measures the widgets that *ignore* Tab rather than the chain. The chain is
    what Qt hands the platform, and it is what a real Tab traverses.
    """
    reachable = set(focusable(surface))
    if not reachable:
        return []
    start = surface.nextInFocusChain()
    order: list[QWidget] = []
    seen: set[QWidget] = set()
    current = start
    # Bounded by the chain's own length: `nextInFocusChain` is a ring, so the walk terminates when
    # it returns to a widget already visited.
    while current is not None and current not in seen:
        seen.add(current)
        if current in reachable:
            order.append(current)
        current = current.nextInFocusChain()
    qapp.processEvents()
    return order


def test_every_verb_the_window_offers_has_a_keyboard_route(composed: MainWindow) -> None:
    """**The global question this task exists to ask** (`T-200`, criterion 1).

    Reachability has been argued one surface at a time and never verified end to end — and the
    window is the surface where it had quietly failed. `QToolBar` gives its buttons `Qt.NoFocus`,
    which is Qt's convention on the assumption that a toolbar *mirrors a menu*; this one mirrors
    nothing. Measured before `T-200`: an empty queue exposed **zero** focusable widgets, the whole
    UI held two shortcuts — `Ctrl+N` and `Ctrl+Q` — and neither was the run control. `UX-006` made
    the queue stopped until started, so a user without a pointer could not download anything.

    **The route, not the tab stop**, is what `NFR-005` asks for and what this asserts. A tab stop
    here is forbidden by `T-234`'s own criterion for a reason that is also about the keyboard, so
    the two rules only look opposed: one says *every verb must be operable without a pointer*, the
    other says *not by taking focus on this bar*.

    Every action the window offers — its menus and its toolbar alike — must therefore be invokable
    by a key: a menu item is reachable through the menu bar, and anything else needs a shortcut.
    """
    menu_items = {
        action
        for menu_action in composed.menuBar().actions()
        if (menu := cast("QMenu | None", menu_action.menu())) is not None
        for action in menu.actions()
        if not action.isSeparator()
    }
    toolbar = composed.findChild(QToolBar, "queueToolBar")
    assert toolbar is not None, "the queue toolbar is gone, so this proves nothing"
    # **A `QWidgetAction` is furniture, not a verb.** The bar's flexible spacer is one — it exists
    # to push `Clear finished` to the right edge and there is nothing for a keyboard to invoke.
    verbs = [
        action
        for action in toolbar.actions()
        if not action.isSeparator() and not isinstance(action, QWidgetAction)
    ]
    assert verbs, "the toolbar carries no verbs at all, so this assertion is vacuous"

    texts = {action.text().replace("&", "") for action in menu_items}
    routeless = [
        action
        for action in verbs
        if action.shortcut().isEmpty() and action.text().replace("&", "") not in texts
    ]
    assert not routeless, (
        "toolbar verb(s) a keyboard cannot invoke — no shortcut and no menu item: "
        f"{[a.objectName() for a in routeless]}"
    )


def test_the_toolbars_two_menuless_verbs_each_have_a_shortcut(composed: MainWindow) -> None:
    """`Start` and `Clear finished` are on no menu, so the shortcut is the route (`T-200`).

    **Asserted as a property, not as two key names.** The rule is *a verb the menus do not carry
    must carry its own shortcut*; naming `Ctrl+R` here would restate `main_window`'s constant and
    pass on whatever it said. A third toolbar verb added later without a menu item fails here.

    The keys themselves are transcribed once, at `RUN_SHORTCUT` and `CLEAR_FINISHED_SHORTCUT`,
    with why they were chosen.
    """
    menu_texts = {
        action.text().replace("&", "")
        for menu_action in composed.menuBar().actions()
        if (menu := cast("QMenu | None", menu_action.menu())) is not None
        for action in menu.actions()
    }
    toolbar = composed.findChild(QToolBar, "queueToolBar")
    assert toolbar is not None, "the queue toolbar is gone, so this proves nothing"

    # **A `QWidgetAction` is furniture, not a verb.** The bar's flexible spacer is one — it exists
    # to push `Clear finished` to the right edge and there is nothing for a keyboard to invoke.
    verbs = [
        action
        for action in toolbar.actions()
        if not action.isSeparator() and not isinstance(action, QWidgetAction)
    ]
    assert verbs, "the toolbar carries no verbs at all"

    routeless = [
        action
        for action in verbs
        if action.text().replace("&", "") not in menu_texts and action.shortcut().isEmpty()
    ]
    assert not routeless, (
        "toolbar verb(s) on no menu and with no shortcut, so a keyboard cannot invoke them: "
        f"{[a.objectName() for a in routeless]}"
    )


def test_no_two_actions_claim_the_same_shortcut(composed: MainWindow) -> None:
    """A collision makes one of two routes silently dead, which is worse than having neither.

    Qt resolves an ambiguous shortcut by doing nothing at all, so the symptom is a key that works
    until a second action claims it and then works for neither.
    """
    bound = [action for action in composed.findChildren(QAction) if not action.shortcut().isEmpty()]
    assert bound, "no action carries a shortcut, so this assertion is vacuous"

    sequences = [action.shortcut().toString() for action in bound]
    duplicates = {key for key in sequences if sequences.count(key) > 1}
    assert not duplicates, (
        f"shortcut(s) claimed by more than one action: {sorted(duplicates)} — "
        f"{[(a.objectName(), a.shortcut().toString()) for a in bound]}"
    )


# --- every surface, not only the window (T-200 criterion 1) -----------------------------------


def surfaces(window: MainWindow, qapp: QApplication) -> list[tuple[str, QWidget]]:
    """Every screen reachable from the window, opened the way a user opens it.

    `open()` rather than `exec()` throughout, which is the application's own choice and the reason
    a test can drive these at all — `open_add_dialog`'s docstring records it.
    """
    opened: list[tuple[str, QWidget]] = [("main window", window)]
    add = window.open_add_dialog()
    qapp.processEvents()
    opened.append(("add dialog", add))
    settings = window.open_settings()
    assert settings is not None, (
        "composition wired no settings writers, so the Settings screen never opened and this "
        "sweep would silently cover one surface fewer"
    )
    qapp.processEvents()
    opened.append(("settings", settings))
    about = window.show_about()
    qapp.processEvents()
    opened.append(("about", about))
    return opened


def test_every_surface_names_every_control_it_publishes(
    composed: MainWindow, qapp: QApplication
) -> None:
    """The name sweep across the whole application, not the window alone (`T-200`).

    A screen signed off on its own is a screen whose labels were checked by whoever wrote it. This
    is the pass that asks the same question of all of them at once, which is the difference between
    this task and the per-surface work `T-107`, `T-110`, `T-181` and `UX-007` already did.
    """
    faults: list[str] = []
    for label, surface in surfaces(composed, qapp):
        nodes = tree_of(surface)
        operable = [node for node in nodes if node.role in OPERABLE_ROLES | NAMED_CONTAINERS]
        if not operable:
            faults.append(f"{label}: publishes no operable control at all")
            continue
        unnamed = [
            node
            for node in operable
            if not is_a_name(node.name) and not is_platform_furniture(node)
        ]
        if unnamed:
            faults.append(f"{label}:\n{describe(unnamed)}")

    assert not faults, "controls with no accessible name:\n" + "\n".join(faults)


def test_every_surface_is_fully_reachable_by_tab(composed: MainWindow, qapp: QApplication) -> None:
    """Reachability across every surface, which is criterion 1 in one assertion.

    Each surface is swept for the widgets a keyboard can land on and then walked through Qt's own
    focus chain; anything focusable the chain never visits is a control a mouse-free user cannot
    operate.
    """
    faults: list[str] = []
    for label, surface in surfaces(composed, qapp):
        expected = set(focusable(surface))
        if not expected:
            # The window is the one surface with no chain, by `T-234`'s criterion; its verbs are
            # asserted by route instead. A *dialog* with nothing focusable would be a real defect,
            # and the coverage floor below is what stops that hiding here.
            continue
        missed = expected - set(tab_order(surface, qapp))
        if missed:
            faults.append(f"{label}: {sorted((type(w).__name__, w.objectName()) for w in missed)}")

    assert not faults, "controls the Tab chain never reaches:\n" + "\n".join(faults)


#: The floor the two sweeps above must clear before their silence means anything.
#:
#: Measured on 2026-08-15: 42 focusable controls and 42 operable nodes across the four surfaces —
#: the Settings screen alone contributes 26 and 23. **Deliberately far below those numbers**, so a
#: surface gaining or losing a control does not fail this, while a sweep that quietly stopped
#: opening the Settings screen — the shape `surfaces()` guards against with its own assertion —
#: cannot pass by inspecting almost nothing. `T-227`'s gate stopping the moment it succeeded is
#: what this is here to prevent.
COVERAGE_FLOOR: Final = 25


@pytest.fixture
def nested_surfaces(qapp: QApplication) -> Iterator[list[tuple[str, QWidget]]]:
    """The screens reached through a staged row's own controls (`T200-R3`).

    **Constructed, not opened, and the difference is stated rather than blurred.** Each of these is
    genuinely reachable — `AddUrlDialog.open_format_table`, `open_template_editor`, `open_options`
    and `open_preset_manager` are the routes — but reaching them needs a *staged row*, which needs a
    real probe against a fixture. That machinery lives in `tests/ui/test_add_dialog.py` and driving
    it here would make an accessibility failure ambiguous with a probe failure.

    **So this checks their names and roles, and claims nothing about their reachability.** The
    routes above are asserted to exist by `test_add_dialog.py`; what was missing until `T200-R3` is
    that **nothing checked these screens were labelled at all** — deleting the format table's
    accessible name left every test here green, because no test had ever looked at it.
    """
    from tracks_and_trails.core.models import FormatInfo
    from tracks_and_trails.core.presets import BUILT_IN_PRESETS
    from tracks_and_trails.core.settings import Settings
    from tracks_and_trails.ui.format_table import FormatTable
    from tracks_and_trails.ui.options_dialog import OptionsDialog
    from tracks_and_trails.ui.playlist_picker import PlaylistPicker
    from tracks_and_trails.ui.preset_manager import PresetManager
    from tracks_and_trails.ui.template_editor import TemplateEditor

    built: list[tuple[str, QWidget]] = [
        # **With a row in it.** An empty table publishes no operable control, and a sweep over
        # nothing is what `T-227`'s gate did the moment it succeeded.
        (
            "format table",
            FormatTable([FormatInfo(format_id="137", extension="mp4", height=1080)]),
        ),
        ("template editor", TemplateEditor("%(title)s.%(ext)s")),
        ("playlist picker", PlaylistPicker()),
        ("options dialog", OptionsDialog(preset=BUILT_IN_PRESETS[0])),
        ("preset manager", PresetManager(Settings(), save=lambda _settings: None)),
    ]
    qapp.processEvents()
    yield built
    # **Owned here, because nothing else owns them** (`T-238`). These are built parentless, and a
    # parentless widget left to the garbage collector has its destructor run inside whichever test
    # comes next — which segfaulted the very next `compose()` when this was a plain function.
    # `T-238`'s guard is the record of that exact shape: *views alive with no parent: zero*.
    for _label, surface in built:
        surface.close()
        surface.deleteLater()
    qapp.processEvents()


def test_every_nested_surface_names_every_control_it_publishes(
    nested_surfaces: list[tuple[str, QWidget]],
) -> None:
    """`T200-R3`: the screens below the add dialog were never inspected at all.

    Removing the format table's accessible name left all eleven earlier tests green, because none
    of them ever built one. A sweep is only a sweep over what it opens.
    """
    faults: list[str] = []
    for label, surface in nested_surfaces:
        nodes = tree_of(surface)
        operable = [node for node in nodes if node.role in OPERABLE_ROLES | NAMED_CONTAINERS]
        if not operable:
            faults.append(f"{label}: publishes no operable control at all")
            continue
        unnamed = [
            node
            for node in operable
            if not is_a_name(node.name) and not is_platform_furniture(node)
        ]
        if unnamed:
            faults.append(f"{label}:\n{describe(unnamed)}")

    assert not faults, "controls with no accessible name:\n" + "\n".join(faults)


def test_every_nested_surface_is_fully_reachable_by_keyboard(
    nested_surfaces: list[tuple[str, QWidget]], qapp: QApplication
) -> None:
    """`T200-R3`: these screens were swept for **names** and never for **reachability**.

    Removing focus from the options dialog's codec control changed nothing, because nothing here
    had ever asked whether a keyboard could get to it. A label on a control nobody can reach is the
    politest possible way to fail `NFR-005`.

    The same two rules the top-level surfaces get: everything Tab can land on, Tab actually reaches;
    and every operable control either takes Tab focus or **declares where its route is**. The
    second is what catches a control being made mouse-only, which is `T200-R2` — and these surfaces
    were outside it.
    """
    faults: list[str] = []
    for label, surface in nested_surfaces:
        expected = set(focusable(surface))
        if not expected:
            faults.append(f"{label}: exposes no control Tab can reach at all")
            continue
        missed = expected - set(tab_order(surface, qapp))
        if missed:
            faults.append(
                f"{label}: Tab never reaches "
                f"{sorted((type(w).__name__, w.objectName()) for w in missed)}"
            )

        for widget in surface.findChildren(QWidget):
            if widget.window() is not surface.window():
                continue
            interface = cast(
                "QAccessibleInterface | None", QAccessible.queryAccessibleInterface(widget)
            )
            if interface is None or interface.role() not in OPERABLE_ROLES:
                continue
            if is_platform_furniture(node_for(widget, interface)):
                continue
            if reaches_by_tab(widget) or widget.property(ROUTE_ELSEWHERE_PROPERTY):
                continue
            faults.append(
                f"{label}: {type(widget).__name__} {widget.objectName()!r} "
                f"({interface.text(QAccessible.Text.Name)!r}) is mouse-only and declares no route"
            )

    assert not faults, "keyboard cannot reach:\n" + "\n".join(faults)


def test_the_sweeps_actually_reach_the_applications_controls(
    composed: MainWindow, qapp: QApplication
) -> None:
    """**A green sweep over nothing is the failure mode this whole file is exposed to.**

    Both sweeps above are assertions that a set is *empty*, and the cheapest way for either to pass
    is to inspect no controls at all. That is not hypothetical here: the first version of the
    reachability test passed over an empty focusable set, because every widget in the window really
    was `Qt.NoFocus`, and it took printing the counts to notice.
    """
    opened = surfaces(composed, qapp)
    operable = sum(
        len([node for node in tree_of(surface) if node.role in OPERABLE_ROLES | NAMED_CONTAINERS])
        for _label, surface in opened
    )
    reachable = sum(len(focusable(surface)) for _label, surface in opened)

    assert operable >= COVERAGE_FLOOR, (
        f"the sweep found {operable} operable controls across {len(opened)} surfaces, under the "
        f"{COVERAGE_FLOOR} floor — it is passing because it is looking at almost nothing"
    )
    assert reachable >= COVERAGE_FLOOR, (
        f"the sweep found {reachable} focusable controls across {len(opened)} surfaces, under the "
        f"{COVERAGE_FLOOR} floor"
    )


def test_no_operable_control_quietly_loses_its_keyboard_route(
    composed: MainWindow, qapp: QApplication
) -> None:
    """**`T200-R2`.** Every sweep above inspects the controls it can *see*, and that is the hole.

    Setting the Settings screen's *Choose folder…* button to `Qt.NoFocus` left all eleven tests
    green: a control that stops being focusable drops out of the focusable set, so the assertion
    that every focusable control is reachable stays true by having one thing fewer to check. **A
    rule that only checks what it can still see cannot notice something being taken away.**

    So this reads the **accessible tree** — which lists the control whether or not it takes focus —
    and requires each operable node to be reachable one of three ways: it takes focus, it is a menu
    item, or it **declares where its route is** through `ui/keyboard.route_is_elsewhere`. The
    declaration is on the widget with its reason, because a list of exempt object names in a test
    is the list that drifts, which is what criterion 4 refuses when it asks for the whole tree
    rather than per widget.
    """
    faults: list[str] = []
    for label, surface in surfaces(composed, qapp):
        for widget in surface.findChildren(QWidget):
            if widget.window() is not surface.window():
                continue
            interface = cast(
                "QAccessibleInterface | None", QAccessible.queryAccessibleInterface(widget)
            )
            if interface is None or interface.role() not in OPERABLE_ROLES:
                continue
            if widget.objectName() in PLATFORM_FURNITURE:
                continue
            if reaches_by_tab(widget):
                continue
            if widget.property(ROUTE_ELSEWHERE_PROPERTY):
                continue
            faults.append(
                f"{label}: {type(widget).__name__} {widget.objectName()!r} "
                f"({interface.text(QAccessible.Text.Name)!r}) takes no focus and declares no route"
            )

    assert not faults, (
        "operable control(s) a keyboard cannot reach, and which do not say where the route went:\n"
        + "\n".join(faults)
    )


# --- focus order and modal return (T-200 criterion 3) -----------------------------------------


def scroll_context(widget: QWidget, surface: QWidget) -> QWidget:
    """The nearest scrolled region `widget` sits in, or `surface` when it sits in none.

    **Positions are only comparable inside one of these.** A `QScrollArea`'s contents live in a
    widget as tall as the content — 1316 px on the Settings screen — while the dialog itself is
    700 px and its fixed footer sits at 716. Comparing the two spaces makes the `Close` button
    look as though it were *above* the controls it follows, which is how the first run of the
    assertion below reported a focus-order defect that is not one. `T-242` is why the footer is
    outside the scroll area at all: the screen has to fit a 1366x768 laptop.
    """
    parent = widget.parentWidget()
    while parent is not None and parent is not surface:
        if isinstance(parent, QScrollArea):
            return parent
        parent = parent.parentWidget()
    return surface


def visual_rows(surface: QWidget, widgets: list[QWidget]) -> list[int]:
    """Each widget's row on screen, counting from the top of `surface`.

    Two controls whose vertical extents overlap are on the **same** row and may be tabbed in
    either order — a label beside its field, a pair of buttons in a footer. Only a jump from a
    lower row back to a higher one is an inversion, which is what the assertion below is about.
    """
    placed = [
        (widget, widget.mapTo(surface, widget.rect().topLeft()).y(), widget.height())
        for widget in widgets
    ]
    rows: list[tuple[int, int]] = []
    for _widget, top, height in sorted(placed, key=lambda item: item[1]):
        bottom = top + max(height, 1)
        if rows and top < rows[-1][1]:
            rows[-1] = (rows[-1][0], max(rows[-1][1], bottom))
            continue
        rows.append((top, bottom))
    return [
        next(index for index, (top, bottom) in enumerate(rows) if top <= y < bottom or y < top)
        for _widget, y, _height in placed
    ]


def test_tab_order_follows_visual_order_on_every_surface(
    composed: MainWindow, qapp: QApplication
) -> None:
    """`T-200` criterion 3: focus order is **asserted**, not just reachability.

    A chain that reaches everything in an order nobody can predict is still a chain a user fights.
    The rule is the ordinary one — the keyboard moves down the surface, not back up it — and
    controls sharing a row may come in either order, because *"the label and its field are on one
    line"* is a layout fact rather than a focus decision.

    `add_dialog`, `format_table`, `template_editor` and `playlist_picker` each call `setTabOrder`
    already; this is the assertion that they agree with what is drawn, and that the surfaces which
    never called it are not relying on luck.
    """
    faults: list[str] = []
    for label, surface in surfaces(composed, qapp):
        # **Controls, not containers** — the same line `OPERABLE_ROLES` draws everywhere else here.
        # A `QScrollArea` accepts focus so the keyboard can scroll it, and Qt puts it *after* its
        # own children in the chain; measured on the Settings screen, that container is the single
        # thing standing between this assertion and a clean order. Demanding it come first would
        # be asserting against Qt rather than against this application's layout.
        order = [
            widget
            for widget in tab_order(surface, qapp)
            if (
                interface := cast(
                    "QAccessibleInterface | None", QAccessible.queryAccessibleInterface(widget)
                )
            )
            is not None
            and interface.role() in OPERABLE_ROLES
        ]
        if len(order) < 2:
            continue
        # Compared **within** each scrolled region, never across one — see `scroll_context`.
        regions: dict[int, list[QWidget]] = {}
        for widget in order:
            regions.setdefault(id(scroll_context(widget, surface)), []).append(widget)

        for group in regions.values():
            if len(group) < 2:
                continue
            rows = visual_rows(surface, group)
            inversions = [
                (
                    group[index].objectName() or type(group[index]).__name__,
                    rows[index],
                    rows[index + 1],
                )
                for index in range(len(rows) - 1)
                if rows[index + 1] < rows[index]
            ]
            if inversions:
                faults.append(f"{label}: Tab moves back up the surface at {inversions}")

    assert not faults, "focus order disagrees with visual order:\n" + "\n".join(faults)


def test_a_modal_returns_focus_to_the_window_that_opened_it(
    composed: MainWindow, qapp: QApplication
) -> None:
    """Closing a dialog must put the user back where they were (`T-200` criterion 3).

    **Asserted through parentage and modality rather than by reading `focusWidget()` after a
    close.** Qt restores focus to the parent window when a modal child closes, and it is the
    parentage that makes it do so — on the offscreen platform there is no window manager to give
    focus back, so a `focusWidget()` assertion would be testing the platform stub rather than the
    application. What this file owns is that each dialog is parented and modal; that Qt honours it
    is Qt's own contract.
    """
    for label, surface in surfaces(composed, qapp)[1:]:
        # **Modality is half the claim, and asserting parentage alone let it go** (`T200-R4`).
        # Changing the add dialog from `open()` to a modeless `show()` passed this test, because a
        # modeless window is parented just the same and simply never takes focus back. Qt returns
        # focus to the parent when a **modal** child closes; without the modality there is nothing
        # to return.
        assert surface.isModal(), (
            f"the {label} is not modal, so closing it hands focus back to nothing — a modeless "
            "window is parented identically and behaves entirely differently"
        )
        assert surface.parent() is not None or surface.parentWidget() is not None, (
            f"the {label} has no parent, so closing it returns focus nowhere"
        )
        assert surface.window() is not composed, (
            f"the {label} is not its own window, so it cannot return focus to one"
        )
        owner = surface.parentWidget()
        assert owner is not None and owner.window() is composed, (
            f"the {label} is parented to {owner!r} rather than to the window that opened it"
        )
