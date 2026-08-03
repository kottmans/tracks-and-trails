"""Open and Show-in-folder, attached to a table (`T-086`, `REQ-021`).

`ui/reveal.py` decides *what argv* and *whether at all*; this is the Qt half — the actions, where
they appear, and what the user is told when nothing opens. **`reveal.py` imports no Qt and this
module holds no launching logic**, which is why the argv tests need no `QApplication` and the
menu tests need no file manager.

## A context menu on each table, not a toolbar button

`REQ-021` names *the history and queue views*, and `T-100` put both on screen at once in a splitter.
A toolbar Open would then be ambiguous — it would act on "the selection", and there are two. The
context menu belongs to the table it was opened on, which removes the question entirely.

`CustomContextMenu` is used rather than overriding `contextMenuEvent` because Qt raises
`customContextMenuRequested` for the **Menu key and Shift+F10** as well as for the mouse, so the
actions are keyboard-reachable without a second code path (`NFR-005`). Double-click opens, which is
what a table of files is expected to do.

## Enabled means it will work

An action is offered only when the selected row has a path recorded. Whether that file still exists
is deliberately *not* part of the enabled state: it would mean a `stat` per selection change, and
the file can vanish between the check and the click regardless. The honest design is to offer it and
report what happened — which `reveal.Refusal` already carries a sentence for.

## Nothing here is modal

A refusal goes to the status bar. A file that has been moved is the *ordinary* case for a history
record (`UX-001`: remove never deletes a file), and a modal dialog for an ordinary case teaches the
user to dismiss dialogs without reading them.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QAbstractItemView, QMenu

from tracks_and_trails.ui.reveal import Refusal, Spawner, Starter, open_file, reveal_file

#: What the two actions are called. "Show in folder" rather than "Reveal": *reveal* is macOS's word
#: for it, and this application does not run there (`REQUIREMENTS.md` §7).
OPEN_TEXT = "&Open file"
REVEAL_TEXT = "Show in &folder"

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
    a context-menu policy, `doubleClicked`, a selection model and a viewport — and history is a
    table while the queue became a list of drawn rows (`T-119`). Naming the narrower type would
    have made this file pick a side in a decision it has no stake in.
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
        platform: str = sys.platform,
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

        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(self._show_menu)
        table.doubleClicked.connect(self.open_selected)
        selection = table.selectionModel()
        if selection is not None:
            selection.selectionChanged.connect(self._selection_changed)
        self._selection_changed()

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
        return refusal

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
