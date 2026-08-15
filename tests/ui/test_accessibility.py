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

## One inventory, and every check walks all of it

`every_surface` is the list of realised screens and **there is exactly one of it** (`T200-R3`).
Each criterion — a name and a role, a keyboard route, a focus order that follows the layout — is
asserted once, over that list.

**This file carried two inventories for three review rounds and that was the defect.** Top-level
screens were opened by one helper, the screens below the add dialog were built by another, and
each check picked whichever list was nearest. The name check grew a nested twin, then the route
check grew one, and the focus-order check never did — so `setTabOrder(embed_subtitles,
audio_codec)` on the options dialog inverted a visible order while all fourteen assertions passed.
Nobody decides to skip a surface; they write the next loop over the list they are already holding.

The surfaces still differ in how they are realised, and the difference is recorded **on the
surface** rather than in the checks — see `Surface`. A check that wants an opinion about which
screens it applies to has to justify it there, where the next reader will see it.

## Driven through the routes a user takes

The top-level screens are opened the way the application opens them — `open_add_dialog()`,
`open_settings()`, `show_about()` — rather than constructed. **`T-201` is why.** Its text was
written, tested and correct for twelve error classes and reached nobody, because the only widget
that composed it was one `UX-005` §2 had left nothing constructing. A pass that instantiates a
screen in order to audit it can pass over a screen no user can open, which is the same defect
wearing this file's clothes.
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
    QAbstractButton,
    QApplication,
    QButtonGroup,
    QComboBox,
    QLabel,
    QLineEdit,
    QMenu,
    QScrollArea,
    QToolBar,
    QWidget,
    QWidgetAction,
)

from tracks_and_trails import app as application
from tracks_and_trails.downloader.ytdlp_service import YtdlpService
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


def radio_group_of(widget: QAbstractButton) -> list[QAbstractButton]:
    """The auto-exclusive buttons `widget` competes with, however the group was formed.

    Qt has two mechanisms and this application uses the implicit one: an explicit `QButtonGroup`,
    or — when there is none — every auto-exclusive sibling under the same parent widget. Both are
    handled, because which one a screen uses is the screen's business and not this file's.

    `group()` is typed as never-`None` and measured to return `None` for all three of the options
    dialog's container radios, which use the implicit mechanism. The same stub-versus-runtime
    mismatch `walk` documents for `interface.object()`, handled the same way: a `cast` says what
    the contract really is, where a `type: ignore` would only silence the check that noticed.
    """
    group = cast("QButtonGroup | None", widget.group())
    if group is not None:
        return list(group.buttons())
    parent = widget.parentWidget()
    if parent is None:
        return [widget]
    return [
        button
        for button in parent.findChildren(QAbstractButton)
        if button.parentWidget() is parent and button.autoExclusive()
    ]


def reached_by_arrows_in_its_group(widget: QWidget) -> bool:
    """Whether Tab reaches `widget`'s radio group and the arrow keys then reach `widget`.

    **Qt takes the `TabFocus` bit off the unchecked members of an auto-exclusive group when the
    surface is shown**, and it does it at show time rather than on construction — measured on the
    options dialog, where all three container radios are policy `11` while unrealised and the two
    unchecked ones are policy `10` once `show()` has run. That is the standard radio-group contract
    on every platform: **Tab enters the group at the checked button and the arrow keys move within
    it**, so a group is one stop rather than three and the keyboard cannot land on an option
    without selecting it.

    **This was invisible to this file until `T200-R3`'s restructure**, and the reason is the finding
    itself: the surfaces below the add dialog were constructed and never realised, so the sweep was
    reading focus policies Qt had not finished deciding. Realising them is what
    `test_tab_order_follows_visual_order_on_every_surface` needs anyway, and it brought this with
    it.

    **Not an exemption, and deliberately not a `route_is_elsewhere` declaration.** That property
    says *this application chose to make a control unfocusable and here is where its route went*;
    this is Qt deciding, after the fact, on a widget whose focus policy the application never
    touched — declaring it would put a sentence about Qt's behaviour on our widget, and would go on
    being true if the group ever became genuinely unreachable. So it is asked as a question with a
    real answer: **is some member of this group reachable by Tab?** A group where none is fails,
    which is the defect this would otherwise hide.
    """
    if not isinstance(widget, QAbstractButton) or not widget.autoExclusive() or widget.isChecked():
        return False
    return any(button.isChecked() and reaches_by_tab(button) for button in radio_group_of(widget))


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


# --- one inventory of realised surfaces (T200-R3) ---------------------------------------------
#
# **This file used to carry two of these and the second one was the defect.** Top-level screens
# were opened by `surfaces()`; the screens below the add dialog were built by a `nested_surfaces`
# fixture; and every check then chose which of the two it looked at. `T200-R3` was reopened twice
# on that shape — the name check grew a nested twin, then the route check grew one, and the
# **focus-order** check never did, so adding `setTabOrder(embed_subtitles, audio_codec)` to
# `OptionsDialog` inverted a visible order while all fourteen assertions passed.
#
# The reviewer named the class rather than the instance: *a gate asks an adjacent implementation
# question rather than the criterion's user-facing question*, four times. Two inventories is how a
# criterion comes to be applied to a subset — nobody decides to skip a surface, they just write the
# next loop over the list they were already holding.
#
# **So there is one inventory now**, and every criterion-owned check walks all of it. A surface
# records how it was realised on itself, because that is a genuine difference between these
# screens; what is not allowed is for a *check* to have an opinion about which ones it applies to.


@dataclass(frozen=True, slots=True)
class Surface:
    """One realised screen, carrying what is genuinely different about it.

    Two of these fields exist because a real difference would otherwise have to live in the checks,
    which is what produced `T200-R3`. Both are properties **of the screen**, and both are asserted
    somewhere rather than merely believed.
    """

    label: str
    widget: QWidget

    #: Whether the application opened it, or this file constructed it.
    #:
    #: The screens below the add dialog are genuinely reachable — `AddUrlDialog.open_format_table`,
    #: `open_template_editor`, `open_options` and `open_preset_manager` are the routes, asserted by
    #: `tests/ui/test_add_dialog.py` — but reaching them needs a *staged row*, which needs a real
    #: probe against a fixture. Driving that here would make an accessibility failure ambiguous
    #: with a probe failure. Everything this file asks of a screen is answerable either way; only
    #: modality, which is a fact about being *opened*, is asked of the opened ones alone.
    opened_through_its_route: bool

    #: Whether Tab is expected to reach anything at all on it.
    #:
    #: **The main window is the one surface where the answer is no, and it is a criterion rather
    #: than a gap** (`T-234`): nothing on its toolbar may take focus, because `T203-R3` recorded a
    #: focusable toolbar widget stealing `Shift+F10` from the row menu on a freshly opened window.
    #: Its verbs are reached by menu and by shortcut, asserted separately below. Every other
    #: surface with an empty chain is a defect, and `test_every_surface_is_fully_reachable_by_tab`
    #: says so.
    expects_a_tab_chain: bool = True


class QuietYtdlp(YtdlpService):
    """A version service that spawns nothing, injected through `compose`'s own seam (`T200-R6`).

    **A widget audit was starting a real yt-dlp child.** `open_settings()` calls `refresh()`, the
    real service answers it by spawning a process and importing yt-dlp, and this file opens the
    Settings screen in every check that walks the inventory. The module printed *"14 passed in
    0.56 s"* and then did not exit within twelve seconds — a passing summary measures assertion
    time, not process completion, and the Implementer's broad suite hid it by doing enough other
    work while those children finished.

    The first correction closed the window through `composition.shutdown.begin()`, which is the
    right lifecycle and does close the manager, the writer, the database and the instance lock —
    but `OrderlyShutdown` does not own this task, so the process still hung. `compose()` has had an
    injection seam for exactly this since `T-198`; this is that seam, used.

    **A subclass rather than a stand-in**, so the signals, the busy state and the guard against two
    operations at once are the production ones and only the three methods that touch a process are
    replaced. `tests/integration/test_composition.py` has one of these for the same reason; it is
    not imported from there because a `tests/ui` module reaching into `tests/integration` couples
    two suites that run separately, and the shared thing would be four lines of stub.
    """

    def __init__(self) -> None:
        super().__init__(directory=Path("/nonexistent-in-tests"))

    def refresh(self) -> None:
        """Answer nothing, and spawn nothing to answer it with."""

    def install_latest_version(self) -> None:
        """Never reached here; overridden so no audit can start an install."""

    def revert(self) -> None:
        """Never reached here; overridden so no audit can start a revert."""


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
        # And nothing is resolved: see `QuietYtdlp` (`T200-R6`).
        ytdlp_service=QuietYtdlp(),
    )
    window = composition.window
    window.show()
    qapp.processEvents()
    yield window
    # **Torn down through the lifecycle composition owns.** Closing the window alone leaves the
    # queue writer and the database open. `shutdown.begin()` is the same route
    # `tests/integration/test_composition.py` drives and the one the application takes when a user
    # closes the window. It does not own the version service, which is why `QuietYtdlp` is above
    # rather than instead of this.
    window.close()
    composition.shutdown.begin()
    deadline = time.monotonic() + 30
    while not composition.shutdown.finished and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    qapp.processEvents()
    assert composition.shutdown.finished, "composition never finished shutting down"


@pytest.fixture
def every_surface(composed: MainWindow, qapp: QApplication) -> Iterator[list[Surface]]:
    """Every screen this application shows, realised, in one list.

    The top-level screens are opened the way the application opens them — `open_add_dialog()`,
    `open_settings()`, `show_about()` — rather than constructed. **`T-201` is why.** Its text was
    written, tested and correct for twelve error classes and reached nobody, because the only
    widget that composed it was one `UX-005` §2 had left nothing constructing. A pass that
    instantiates a screen in order to audit it can pass over a screen no user can open.

    The screens below the add dialog are constructed, for the reason recorded on
    `Surface.opened_through_its_route`, and **shown**: geometry is what
    `test_tab_order_follows_visual_order_on_every_surface` compares, and an unrealised widget has
    none worth comparing.
    """
    from tracks_and_trails.core.models import FormatInfo
    from tracks_and_trails.core.presets import BUILT_IN_PRESETS
    from tracks_and_trails.core.settings import Settings
    from tracks_and_trails.ui.format_table import FormatTable
    from tracks_and_trails.ui.options_dialog import OptionsDialog
    from tracks_and_trails.ui.playlist_picker import PlaylistPicker
    from tracks_and_trails.ui.preset_manager import PresetManager
    from tracks_and_trails.ui.template_editor import TemplateEditor

    inventory: list[Surface] = [
        Surface(
            "main window",
            composed,
            opened_through_its_route=True,
            expects_a_tab_chain=False,
        )
    ]

    add = composed.open_add_dialog()
    qapp.processEvents()
    inventory.append(Surface("add dialog", add, opened_through_its_route=True))

    settings = composed.open_settings()
    assert settings is not None, (
        "composition wired no settings writers, so the Settings screen never opened and this "
        "sweep would silently cover one surface fewer"
    )
    qapp.processEvents()
    inventory.append(Surface("settings", settings, opened_through_its_route=True))

    about = composed.show_about()
    qapp.processEvents()
    inventory.append(Surface("about", about, opened_through_its_route=True))

    built: list[tuple[str, QWidget]] = [
        # **With a row in it.** An empty table publishes no operable control, and a sweep over
        # nothing is what `T-227`'s gate did the moment it succeeded.
        ("format table", FormatTable([FormatInfo(format_id="137", extension="mp4", height=1080)])),
        ("template editor", TemplateEditor("%(title)s.%(ext)s")),
        ("playlist picker", PlaylistPicker()),
        ("options dialog", OptionsDialog(preset=BUILT_IN_PRESETS[0])),
        ("preset manager", PresetManager(Settings(), save=lambda _settings: None)),
    ]
    for label, widget in built:
        widget.show()
        inventory.append(Surface(label, widget, opened_through_its_route=False))
    qapp.processEvents()

    yield inventory

    # **The constructed ones are owned here, because nothing else owns them** (`T-238`). They are
    # built parentless, and a parentless widget left to the garbage collector has its destructor
    # run inside whichever test comes next — which segfaulted the very next `compose()` when this
    # was a plain function. `T-238`'s guard is the record of that exact shape: *views alive with no
    # parent: zero*.
    for _label, widget in built:
        widget.close()
        widget.deleteLater()
    qapp.processEvents()


#: The floor the whole-application sweeps must clear before their silence means anything.
#:
#: **Measured 2026-08-15 across the nine surfaces of the inventory**: 81 operable nodes, 65
#: focusable widgets, 59 operable widgets reached by the route check.
#: `test_the_sweeps_actually_reach_the_applications_controls` prints the per-surface breakdown when
#: it fails, so this can be re-derived rather than guessed at the next time it moves.
#:
#: **Set so that losing the largest surface fails it.** The Settings screen contributes 25 of each,
#: and a sweep that quietly stopped opening it would come back with 34 and 40 — both under this.
#: That is the shape being guarded: not a control added or removed, which should never fail a
#: floor, but a whole screen dropping out unnoticed. `T-227`'s gate stopping the moment it
#: succeeded is the precedent.
#:
#: The floor is the **aggregate** guard and it is the weaker half: per-surface non-vacuity is
#: asserted by each check as it goes, which is what stops one missing surface hiding behind eight
#: present ones.
COVERAGE_FLOOR: Final = 42


def operable_nodes(surface: Surface) -> list[Node]:
    """The nodes on one surface that this file holds to a name."""
    return [
        node for node in tree_of(surface.widget) if node.role in OPERABLE_ROLES | NAMED_CONTAINERS
    ]


def operable_widgets(surface: Surface) -> Iterator[tuple[QWidget, QAccessibleInterface]]:
    """Every widget on one surface that a user operates, with the interface that describes it.

    Scoped to the surface's own window, for `focusable`'s reason: a dialog is *parented* to the
    window that opened it, so `findChildren` otherwise walks straight into it.
    """
    for widget in surface.widget.findChildren(QWidget):
        if widget.window() is not surface.widget.window():
            continue
        interface = cast(
            "QAccessibleInterface | None", QAccessible.queryAccessibleInterface(widget)
        )
        if interface is None or interface.role() not in OPERABLE_ROLES:
            continue
        yield widget, interface


# --- names and roles (T-200 criterion 4) ------------------------------------------------------


def test_every_surface_names_every_control_it_publishes(every_surface: list[Surface]) -> None:
    """`NFR-005`, over the whole tree of every screen rather than a list of widgets.

    **A per-widget list is a list that drifts** — the criterion says so in as many words, and this
    project has the receipts: `T-235` found the queue's run control had never been in the Windows
    sweep at all, because that sweep enumerated roles and the control had a role nobody had thought
    of. So this walks what Qt publishes and holds every operable node to the same rule.

    A screen signed off on its own is a screen whose labels were checked by whoever wrote it. This
    is the pass that asks the same question of all of them at once, which is the difference between
    this task and the per-surface work `T-107`, `T-110`, `T-181` and `UX-007` already did.
    """
    faults: list[str] = []
    for surface in every_surface:
        operable = operable_nodes(surface)
        # **Per-surface non-vacuity, checked here rather than by the aggregate floor.** One
        # surface publishing nothing is exactly what an aggregate hides.
        if not operable:
            faults.append(f"{surface.label}: publishes no operable control at all")
            continue
        unnamed = [
            node
            for node in operable
            if not is_a_name(node.name) and not is_platform_furniture(node)
        ]
        if unnamed:
            faults.append(f"{surface.label}:\n{describe(unnamed)}")

    assert not faults, "controls with no accessible name:\n" + "\n".join(faults)


def test_no_control_is_published_without_a_role(every_surface: list[Surface]) -> None:
    """A name with no role is announced as *"Start"* and nothing else — a word, not a control.

    `QAccessible.Role.NoRole` is the value Qt uses when it has nothing to say, so a named node
    carrying it is a control the bridge cannot classify.
    """
    faults: list[str] = []
    for surface in every_surface:
        named = [node for node in tree_of(surface.widget) if node.name.strip()]
        assert named, f"{surface.label}: publishes no named node at all"
        roleless = [node for node in named if node.role == QAccessible.Role.NoRole]
        if roleless:
            faults.append(f"{surface.label}:\n{describe(roleless)}")

    assert not faults, "named control(s) published with no role:\n" + "\n".join(faults)


def test_every_focusable_control_is_named(every_surface: list[Surface]) -> None:
    """The same rule from the widget side, which catches what the tree flattens.

    A `QAccessible` tree is not one node per widget: Qt merges, promotes and hides. A control can
    therefore be focusable — a user tabs to it, and a screen reader is asked to say what it is —
    while contributing no operable node for the sweep above to inspect.
    """
    unnamed: list[str] = []
    for surface in every_surface:
        for widget in focusable(surface.widget):
            if widget.objectName() in PLATFORM_FURNITURE:
                continue
            interface = cast(
                "QAccessibleInterface | None", QAccessible.queryAccessibleInterface(widget)
            )
            # A container that merely accepts focus so its children can be reached announces itself
            # by role; the rule is about controls, and `OPERABLE_ROLES` is where that line is drawn.
            if interface is None or interface.role() not in OPERABLE_ROLES:
                continue
            # **Asked of the interface, not of the widget** — `widget.accessibleName()` is the wrong
            # object for half these controls. A `QToolBar` builds its buttons from `QAction`s and
            # the *action* carries the text, so `Start` and `Clear finished` have an empty
            # `accessibleName()` and a perfectly good published name. Asserting the widget's own
            # field would have demanded a second copy of a name that is already right, which is how
            # a rule ends up making an application worse to satisfy it.
            if not is_a_name(interface.text(QAccessible.Text.Name)):
                unnamed.append(f"{surface.label}: {type(widget).__name__} {widget.objectName()!r}")

    assert not unnamed, "focusable control(s) with no accessible name: " + ", ".join(unnamed)


def buddy_label_of(widget: QWidget) -> str:
    """The text of the `QLabel` that declares `widget` as its buddy, or `""`.

    **The buddy is what produces the `Label` relation a screen reader reads**, and it is asked from
    the widget side rather than by walking `interface.relations()` because a control gets a
    relation for its enclosing `QGroupBox` as well. Both arrive as `Label`, in an order nothing
    documents, and *"the section this sits in"* is not a name for the control — that is exactly the
    confusion `T200-R7` is about. A buddy is declared deliberately by whoever built the screen.
    """
    window = widget.window()
    for label in window.findChildren(QLabel):
        if label.buddy() is widget:
            return label.text()
    return ""


def test_no_control_is_named_only_by_the_value_it_happens_to_hold(
    every_surface: list[Surface],
) -> None:
    """**`T200-R7`.** A control has to say what it is *for*, not only what it currently holds.

    **`QComboBox` publishes its selected item as its accessible name and discards
    `setAccessibleName` entirely** — on this platform, by Qt's design.
    `QAccessibleComboBox::text` falls through `Name` to `Value` under `Q_OS_UNIX`, and the upstream
    comment says why: *"on Linux we use relations for this, name is text"*. So the supported
    mechanism here is the `Label` relation, and a combo without a buddy has **no name at all** —
    it has a value standing where its name should be.

    Measured before this rule existed: the Settings preset picker announced *"Best video up to
    1080p (MP4)"* as both its name and its value, and deleting its accessible name changed nothing
    the sweep could see, because `is_a_name` found words in the preset's title. **A rule that asks
    only whether a string contains a word cannot tell a purpose from a selection.**

    Worse, two controls announced the *same* name: the add dialog's preset picker and its bitrate
    picker had no labels at all, so the only relation either could offer was the group box they
    share — *"Download as"* — for two different choices.

    **So both fields are checked.** Where the published name is the value, the name has to come
    from a buddy; and the value still has to be the selection, so this cannot be satisfied by
    breaking the value instead.
    """
    faults: list[str] = []
    checked = 0
    for surface in every_surface:
        for widget, interface in operable_widgets(surface):
            if is_platform_furniture(node_for(widget, interface)):
                continue
            name = interface.text(QAccessible.Text.Name)
            value = interface.text(QAccessible.Text.Value)
            if not value or name != value:
                # The control publishes a name of its own — the ordinary case, and every role
                # except `QComboBox` measured on this platform.
                continue
            checked += 1
            buddy = buddy_label_of(widget)
            where = f"{surface.label}: {type(widget).__name__} {widget.objectName()!r}"
            if not is_a_name(buddy):
                faults.append(
                    f"{where} publishes {name!r} as both its name and its value, and no label "
                    "declares it as a buddy — so nothing says what it is for"
                )
            # **The widget's own field is asked for as well, and only here** (`T200-R7`). Everywhere
            # else in this file the interface is the right object to ask; for these controls it is
            # the right object on *one* platform. The fall-through that hides `accessibleName` is
            # `Q_OS_UNIX`-only, so Windows reads `QAccessibleWidget::text` and gets this field —
            # which `tests/ui/test_windows_accessibility.py` checks through real UI Automation and
            # this file cannot. Requiring both is what stops a fix for the platform under test from
            # silently emptying the name on the platform that is not.
            if not is_a_name(widget.accessibleName()):
                faults.append(
                    f"{where} has no accessibleName of its own — the buddy names it on Linux, and "
                    "Windows reads this field instead, so dropping it moves the gap rather than "
                    "closing it"
                )
            if isinstance(widget, QComboBox) and value != widget.currentText():
                faults.append(f"{where} publishes {value!r} as its value, not its selection")

    assert checked, (
        "no control was found publishing its value as its name, so this rule inspected nothing — "
        "if Qt stopped doing that, delete this test rather than letting it pass in silence"
    )
    assert not faults, "control(s) named only by what they hold:\n" + "\n".join(faults)


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


def test_every_surface_is_fully_reachable_by_tab(
    every_surface: list[Surface], qapp: QApplication
) -> None:
    """Reachability across every surface, which is criterion 1 in one assertion.

    Each surface is swept for the widgets a keyboard can land on and then walked through Qt's own
    focus chain; anything focusable the chain never visits is a control a mouse-free user cannot
    operate.

    **An empty chain is a defect everywhere except the main window**, where `T-234` requires it —
    and that exception is declared on the surface rather than decided here, so a dialog that
    quietly stops offering a chain fails instead of being skipped.
    """
    faults: list[str] = []
    for surface in every_surface:
        expected = set(focusable(surface.widget))
        if not expected:
            if surface.expects_a_tab_chain:
                faults.append(f"{surface.label}: exposes no control Tab can reach at all")
            continue
        assert not surface.expects_a_tab_chain or expected, surface.label
        missed = expected - set(tab_order(surface.widget, qapp))
        if missed:
            faults.append(
                f"{surface.label}: Tab never reaches "
                f"{sorted((type(w).__name__, w.objectName()) for w in missed)}"
            )

    assert not faults, "controls the Tab chain never reaches:\n" + "\n".join(faults)


def test_no_operable_control_quietly_loses_its_keyboard_route(
    every_surface: list[Surface],
) -> None:
    """**`T200-R2`.** Every sweep above inspects the controls it can *see*, and that is the hole.

    Setting the Settings screen's *Choose folder…* button to `Qt.NoFocus` left all eleven tests of
    the first submission green: a control that stops being focusable drops out of the focusable
    set, so the assertion that every focusable control is reachable stays true by having one thing
    fewer to check. **A rule that only checks what it can still see cannot notice something being
    taken away.** `Qt.ClickFocus` then did the same thing one property along, which is why
    `reaches_by_tab` asks for the `TabFocus` capability rather than for a policy that is not
    `NoFocus`.

    So this reads the **accessible tree** — which lists the control whether or not it takes focus —
    and requires each operable node to be reachable one of three ways: it takes focus, it is a menu
    item, or it **declares where its route is** through `ui/keyboard.route_is_elsewhere`. The
    declaration is on the widget with its reason, because a list of exempt object names in a test
    is the list that drifts, which is what criterion 4 refuses when it asks for the whole tree
    rather than per widget.
    """
    faults: list[str] = []
    inspected = 0
    for surface in every_surface:
        for widget, interface in operable_widgets(surface):
            if is_platform_furniture(node_for(widget, interface)):
                continue
            inspected += 1
            if (
                reaches_by_tab(widget)
                or reached_by_arrows_in_its_group(widget)
                or widget.property(ROUTE_ELSEWHERE_PROPERTY)
            ):
                continue
            faults.append(
                f"{surface.label}: {type(widget).__name__} {widget.objectName()!r} "
                f"({interface.text(QAccessible.Text.Name)!r}) takes no focus and declares no route"
            )

    assert inspected >= COVERAGE_FLOOR, (
        f"only {inspected} operable control(s) were inspected across {len(every_surface)} "
        f"surfaces, under the {COVERAGE_FLOOR} floor — this passed by looking at almost nothing"
    )
    assert not faults, (
        "operable control(s) a keyboard cannot reach, and which do not say where the route went:\n"
        + "\n".join(faults)
    )


def test_every_toolbar_verb_has_a_menu_item_or_a_shortcut(composed: MainWindow) -> None:
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

    **Asserted as a property, not as two key names.** The rule is *a verb the menus do not carry
    must carry its own shortcut*; naming `Ctrl+R` here would restate `main_window`'s constant and
    pass on whatever it said. A third toolbar verb added later without a menu item fails here.

    *(This was two tests until `T200-R3`'s restructure —
    `test_every_verb_the_window_offers_has_a_keyboard_route` and
    `test_the_toolbars_two_menuless_verbs_each_have_a_shortcut` — whose `routeless` predicates were
    the same conjunction in the opposite order. Merged rather than left as a second copy that could
    drift from the first; the shortcut constants keep their own regression in
    `tests/ui/test_main_window.py`.)*
    """
    menu_texts = {
        action.text().replace("&", "")
        for menu_action in composed.menuBar().actions()
        if (menu := cast("QMenu | None", menu_action.menu())) is not None
        for action in menu.actions()
        if not action.isSeparator()
    }
    assert menu_texts, "the menu bar publishes no actions, so this proves nothing"

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

    routeless = [
        action
        for action in verbs
        if action.shortcut().isEmpty() and action.text().replace("&", "") not in menu_texts
    ]
    assert not routeless, (
        "toolbar verb(s) a keyboard cannot invoke — no shortcut and no menu item: "
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


#: How many surfaces must actually be compared before a clean focus-order sweep means anything.
#:
#: A surface with fewer than two ordered controls cannot invert, so it is skipped — and a skip is
#: indistinguishable from a pass, which is the whole reason `T200-R3` survived three rounds.
#:
#: **Measured 2026-08-15: five surfaces are compared** — the add dialog, Settings, the template
#: editor, the options dialog and the preset manager. **Three of the five are constructed ones**,
#: so a change that stopped realising them would leave two and fail this, which is precisely the
#: regression to guard against: the mutation that proves this check works lives on the options
#: dialog, and an unrealised options dialog would stop catching it silently.
ORDERED_SURFACE_FLOOR: Final = 4


def test_tab_order_follows_visual_order_on_every_surface(
    every_surface: list[Surface], qapp: QApplication
) -> None:
    """`T-200` criterion 3: focus order is **asserted**, not just reachability.

    A chain that reaches everything in an order nobody can predict is still a chain a user fights.
    The rule is the ordinary one — the keyboard moves down the surface, not back up it — and
    controls sharing a row may come in either order, because *"the label and its field are on one
    line"* is a layout fact rather than a focus decision.

    `add_dialog`, `format_table`, `template_editor` and `playlist_picker` each call `setTabOrder`
    already; this is the assertion that they agree with what is drawn, and that the surfaces which
    never called it are not relying on luck.

    **This is the check `T200-R3` was reopened twice for.** It ran over the top-level surfaces
    alone while the name and route checks grew nested twins, so
    `setTabOrder(embed_subtitles, audio_codec)` on `OptionsDialog` inverted a visible order and all
    fourteen assertions passed. It walks the one inventory now, which is the restructure rather
    than a third twin.
    """
    faults: list[str] = []
    compared: list[str] = []
    for surface in every_surface:
        # **Controls, not containers** — the same line `OPERABLE_ROLES` draws everywhere else here.
        # A `QScrollArea` accepts focus so the keyboard can scroll it, and Qt puts it *after* its
        # own children in the chain; measured on the Settings screen, that container is the single
        # thing standing between this assertion and a clean order. Demanding it come first would
        # be asserting against Qt rather than against this application's layout.
        order = [
            widget
            for widget in tab_order(surface.widget, qapp)
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
        compared.append(surface.label)
        # Compared **within** each scrolled region, never across one — see `scroll_context`.
        regions: dict[int, list[QWidget]] = {}
        for widget in order:
            regions.setdefault(id(scroll_context(widget, surface.widget)), []).append(widget)

        for group in regions.values():
            if len(group) < 2:
                continue
            rows = visual_rows(surface.widget, group)
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
                faults.append(f"{surface.label}: Tab moves back up the surface at {inversions}")

    assert len(compared) >= ORDERED_SURFACE_FLOOR, (
        f"only {len(compared)} of {len(every_surface)} surfaces had two or more ordered controls "
        f"to compare, under the {ORDERED_SURFACE_FLOOR} floor — a screen that stopped being "
        f"realised would be skipped here rather than failing. Compared: {compared}"
    )
    assert not faults, "focus order disagrees with visual order:\n" + "\n".join(faults)


def test_a_modal_returns_focus_to_the_window_that_opened_it(every_surface: list[Surface]) -> None:
    """Closing a dialog must put the user back where they were (`T-200` criterion 3).

    **Asserted through parentage and modality rather than by reading `focusWidget()` after a
    close.** Qt restores focus to the parent window when a modal child closes, and it is the
    parentage that makes it do so — on the offscreen platform there is no window manager to give
    focus back, so a `focusWidget()` assertion would be testing the platform stub rather than the
    application. What this file owns is that each dialog is parented and modal; that Qt honours it
    is Qt's own contract.

    **This is the one check that asks only the opened surfaces**, and it is a fact about being
    opened rather than a preference about which screens are worth checking: a screen this file
    constructed was never handed focus, so it has none to hand back.
    """
    window = every_surface[0].widget
    dialogs = [surface for surface in every_surface[1:] if surface.opened_through_its_route]
    assert dialogs, "no dialog was opened, so this assertion is vacuous"

    for surface in dialogs:
        # **Modality is half the claim, and asserting parentage alone let it go** (`T200-R4`).
        # Changing the add dialog from `open()` to a modeless `show()` passed this test, because a
        # modeless window is parented just the same and simply never takes focus back. Qt returns
        # focus to the parent when a **modal** child closes; without the modality there is nothing
        # to return.
        assert surface.widget.isModal(), (
            f"the {surface.label} is not modal, so closing it hands focus back to nothing — a "
            "modeless window is parented identically and behaves entirely differently"
        )
        assert surface.widget.window() is not window, (
            f"the {surface.label} is not its own window, so it cannot return focus to one"
        )
        owner = surface.widget.parentWidget()
        assert owner is not None and owner.window() is window, (
            f"the {surface.label} is parented to {owner!r} rather than to the window that opened it"
        )


# --- the sweeps are not passing over nothing --------------------------------------------------


def test_every_surface_in_the_inventory_is_realised(every_surface: list[Surface]) -> None:
    """**`Qt` decides part of what this file measures at show time**, so it has to be shown.

    Measured 2026-08-15 on the options dialog: its three container radios are all focus policy
    `11` — `StrongFocus | WheelFocus` — while unrealised, and the two *unchecked* ones drop to
    `10` once `show()` has run, because Qt takes the `TabFocus` bit off the losing members of an
    auto-exclusive group. **An unrealised sweep therefore reports two controls as Tab-reachable
    that a real session does not**, and it reports them as reachable in the direction that passes.

    That is this task's own defect class one layer down: not a check looking at the wrong screens,
    but a check looking at the right screens in a state no user is ever in. Realisation is the
    premise every other assertion here rests on, so it is asserted rather than assumed —
    deleting `show()` from the fixture otherwise leaves all ten of these green, which is measured
    rather than supposed.
    """
    unrealised = [surface.label for surface in every_surface if not surface.widget.isVisible()]
    assert not unrealised, (
        f"surface(s) audited without being realised: {unrealised} — Qt has not finished deciding "
        "their focus policies, so what this file would measure is not what a user meets"
    )


def test_the_sweeps_actually_reach_the_applications_controls(
    every_surface: list[Surface],
) -> None:
    """**A green sweep over nothing is the failure mode this whole file is exposed to.**

    Most assertions above are that a set is *empty*, and the cheapest way for any of them to pass
    is to inspect no controls at all. That is not hypothetical here: the first version of the
    reachability test passed over an empty focusable set, because every widget in the window really
    was `Qt.NoFocus`, and it took printing the counts to notice.

    Per-surface non-vacuity is asserted by each check as it goes; this is the aggregate, and it
    prints what it measured so the floors above can be re-derived rather than guessed at.
    """
    operable = sum(len(operable_nodes(surface)) for surface in every_surface)
    reachable = sum(len(focusable(surface.widget)) for surface in every_surface)
    per_surface = {
        surface.label: (len(operable_nodes(surface)), len(focusable(surface.widget)))
        for surface in every_surface
    }

    assert operable >= COVERAGE_FLOOR, (
        f"the sweep found {operable} operable controls across {len(every_surface)} surfaces, under "
        f"the {COVERAGE_FLOOR} floor — it is passing because it is looking at almost nothing: "
        f"{per_surface}"
    )
    assert reachable >= COVERAGE_FLOOR, (
        f"the sweep found {reachable} focusable controls across {len(every_surface)} surfaces, "
        f"under the {COVERAGE_FLOOR} floor: {per_surface}"
    )
