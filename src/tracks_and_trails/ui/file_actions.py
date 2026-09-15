"""Open and Show-in-folder, attached to a table (`T-086`, `REQ-021`).

`ui/reveal.py` decides *what argv* and *whether at all*; this is the Qt half — the actions, where
they appear, and what the user is told when nothing opens. **`reveal.py` imports no Qt and this
module holds no launching logic**, which is why the argv tests need no `QApplication` and the
menu tests need no file manager.

## A context menu on each table, not a toolbar button

`REQ-021` names *the history and queue views*, and `T-100` put both on screen at once in a splitter.
A toolbar Open was ambiguous while that held — it would act on "the selection", and there were two.
The context menu belongs to the table it was opened on, which removed the question entirely.

*(Written when there were two tables. History went with `T-169`/`T-170`, so there is one selection
now and the ambiguity this argument answers no longer arises. Kept because the arrangement it chose
is still the one in place, and because a second table is what `REQ-021` would need again —
`T-186`, which found this paragraph still saying "there are two" in the present tense.)*

`CustomContextMenu` is used rather than overriding `contextMenuEvent` because Qt raises
`customContextMenuRequested` for the **Menu key and Shift+F10** as well as for the mouse, so the
actions are keyboard-reachable without a second code path (`NFR-005`). Double-click opens, which is
what a table of files is expected to do.

## Enabled means it will work

An action is offered only when the selected row has a path recorded. Whether that file still exists
is deliberately *not* part of the enabled state: it would mean a `stat` per selection change, and
the file can vanish between the check and the click regardless. The honest design is to offer it and
report what happened — which `reveal.Refusal` already carries a sentence for.

## A refusal is a message box the user closes (`T-346`)

A refusal goes to the status bar, and **to a message box**. It was a tooltip at the row (`T-158`,
which found the status bar alone was not read), and that did not work either: on KDE the tooltip was
hidden the moment the menu that triggered it closed, so it showed for a fraction of a second, and as
one long line it ran off the screen. The maintainer chose the box on 2026-09-15, over keeping the
status bar alone.

The earlier reasoning against a modal box, that a moved file is the ordinary case and a dialog for
it teaches dismissing dialogs, is outweighed by what happened: a notice nobody could read. The box
follows a click the user just made, so it answers that click rather than interrupting anything.
The window's box also offers **Remove from queue** for a missing file, which is the one thing a
user can do about it from here.

**One sentence.** `Refusal.reason` is written once in `reveal.py`, and the box and the status bar
show it unchanged.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QAbstractItemView, QMenu, QMessageBox

from tracks_and_trails.ui.reveal import Refusal, Spawner, Starter, open_file, reveal_file


class RefusalShower(Protocol):
    """Tells the user why nothing opened (`T-346`). The window supplies one; see `FileActions`."""

    def __call__(self, refusal: Refusal, /) -> object: ...


#: What the two actions are called. "Show in folder" rather than "Reveal": *reveal* is macOS's word
#: for it, and this application does not run there (`REQUIREMENTS.md` §7).
OPEN_TEXT = "&Open file"
REVEAL_TEXT = "Show in &folder"

#: The titles of the box that says why nothing opened (`T-346`).
FILE_NOT_FOUND_TITLE = "File not found"
COULD_NOT_OPEN_TITLE = "Could not open the file"

#: How long a refusal stays in the status bar. Long enough to read a sentence, short enough that it
#: does not become permanent furniture.
MESSAGE_TIMEOUT_MS = 10_000


class FileActions(QObject):
    """Open and Show-in-folder for whichever row `table` has selected.

    Every collaborator is a callable rather than an object, for `ARCHITECTURE.md` §3's reason and
    one more: `output_directory` is read at the moment of use, not captured, because `T-079` lets
    the user change it while the window is open — and containment is checked against wherever
    downloads go *now*.

    **`QAbstractItemView`, not `QTableView`.** Nothing here uses more than the base class offers —
    a context-menu policy, `doubleClicked`, a selection model and a viewport. It was written
    while History was a table and the queue was becoming a list of drawn rows (`T-119`), so naming
    the narrower type would have made this file pick a side in a decision it had no stake in.
    **History is gone and the reason survives it**: this file still has no stake in how its view
    is built.  *(`T-176`: the sentence was present tense about a surface removed on 2026-08-06.)*
    """

    def __init__(
        self,
        *,
        table: QAbstractItemView,
        selected_path: Callable[[], str | None],
        output_directory: Callable[[], Path],
        report: Callable[[str], None],
        run: Spawner | None = None,
        start: Starter | None = None,
        show_refusal: RefusalShower | None = None,
        platform: str = sys.platform,
        context_menu: bool = True,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._table = table
        self._selected_path = selected_path
        self._output_directory = output_directory
        self._report = report
        #: The launcher, injected for the reason `reveal.Spawner` gives — and needed *here* too,
        #: not only one layer down: without it a test that triggers the action opens a real file
        #: manager on the machine running the suite, which is both slow and a test of that machine.
        self._run = run
        #: The **Windows Open** seam, which is a different route entirely (`T086-R1`). Without it
        #: the Windows CI job would call the real `os.startfile` and launch a media player on a
        #: build agent — the same hazard `run` exists to prevent, on the branch that has no argv.
        self._start = start
        #: **How a refusal is shown** (`T-346`): a message box the user closes. The window passes
        #: its own, which offers *Remove from queue* for a missing file; without one, a plain box.
        #: **Not a bound method as the default**, which would be a reference cycle through this
        #: object, and the suite's widget-lifetime check finds the table then reachable only through
        #: that cycle (`T-289`'s hazard). `None` means the plain box, chosen when a refusal happens.
        self._show_refusal = show_refusal
        #: Pinned by tests so the **Windows** route is exercised from Linux, for the reason
        #: `ui/reveal.py`'s module docstring gives. Without it, dropping the `start` seam below is
        #: invisible on any POSIX machine — a mutation doing exactly that survived until this
        #: parameter existed.
        self._platform = platform

        self._open = QAction(OPEN_TEXT, self)
        self._open.setObjectName("openFileAction")
        self._open.setStatusTip("Open the selected download in its usual application")
        self._open.triggered.connect(self.open_selected)

        self._reveal = QAction(REVEAL_TEXT, self)
        self._reveal.setObjectName("revealFileAction")
        self._reveal.setStatusTip("Show the selected download in your file manager")
        self._reveal.triggered.connect(self.reveal_selected)

        # **Only when nothing else owns that channel** (`T124-R1`). A table has one
        # `customContextMenuRequested`, and `UX-005` §4 gives it to the row's `⋯` menu — which
        # already carries *Open* and *Show in folder* for the rows that have a file, through these
        # very actions, and carries the rest of the row's verbs besides. Connecting both popped two
        # menus on one gesture. The shell therefore passes `context_menu=False` and builds one
        # menu; anything constructing `FileActions` over a table of its own keeps the default and
        # keeps a keyboard-reachable menu.
        if context_menu:
            table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            table.customContextMenuRequested.connect(self._show_menu)
        table.doubleClicked.connect(self.open_selected)
        selection = table.selectionModel()
        if selection is not None:
            selection.selectionChanged.connect(self._selection_changed)
        self._selection_changed()

    @property
    def table(self) -> QAbstractItemView:
        """The view these actions belong to.

        Exposed because the shell holds one set **per table** (`REQ-021` names both views and both
        are reachable), so a caller acting on a named row has to find the set that owns that row's
        table. Asking the object which table it serves is `T118-R13`'s lesson: a caller that
        matched by position or by name would be right until the order changed.
        """
        return self._table

    @property
    def open_action(self) -> QAction:
        return self._open

    @property
    def reveal_action(self) -> QAction:
        return self._reveal

    def open_selected(self, *_: object) -> Refusal | None:
        """Open the selected row's file. Returns the refusal it reported, or `None`.

        Returned *and* reported: the return value is what a test reads, and a test that only
        scraped the status bar would pass against a handler that reported the wrong sentence.
        """
        return self._act(
            lambda path, within: open_file(
                path,
                within=within,
                run=self._run,
                start=self._start,
                platform=self._platform,
            )
        )

    def reveal_selected(self, *_: object) -> Refusal | None:
        """Show the selected row's file in the file manager.

        **Takes no `start`**, and that asymmetry is the point of `T086-R1`: Reveal is `explorer
        /select,` on Windows and a D-Bus call on Linux, both of which are commands. Open is an
        associated-application API on Windows. One seam each rather than one seam pretending to
        cover both.
        """
        return self._act(lambda path, within: reveal_file(path, within=within, run=self._run))

    def _act(self, launch: Callable[[Path, Path], Refusal | None]) -> Refusal | None:
        path = self._selected_path()
        if not path:
            # No selection, or a row with no path recorded — the actions are disabled in both
            # cases, and this is the keyboard-shortcut route that the enabled state does not cover.
            return None
        refusal = launch(Path(path), self._output_directory())
        if refusal is not None:
            self._report(refusal.reason)
            if self._show_refusal is not None:
                self._show_refusal(refusal)
            else:
                self._show_plain_box(refusal)
        return refusal

    def _show_plain_box(self, refusal: Refusal) -> QMessageBox:
        """A message box saying why nothing opened, for a host that supplied no `show_refusal`."""
        box = QMessageBox(self._table.window())
        box.setObjectName("fileRefusalDialog")
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(FILE_NOT_FOUND_TITLE if refusal.missing else COULD_NOT_OPEN_TITLE)
        box.setText(refusal.reason)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        box.open()
        return box

    def _selection_changed(self, *_: object) -> None:
        """Offer the actions only for a row that has a path (see the module docstring)."""
        enabled = bool(self._selected_path())
        self._open.setEnabled(enabled)
        self._reveal.setEnabled(enabled)

    def _show_menu(self, position: QPoint) -> QMenu:
        """The context menu, built fresh so it always reflects the current enabled state.

        Returned so a test can inspect it. `popup` rather than `exec` because `exec` blocks in a
        nested event loop, which a test cannot get out of.
        """
        menu = QMenu(self._table)
        menu.setObjectName("fileActionsMenu")
        menu.addAction(self._open)
        menu.addAction(self._reveal)
        menu.popup(self._table.viewport().mapToGlobal(position))
        return menu
