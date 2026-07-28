"""T-026 mutation class 2: a focusable control that nobody declared, in the dialog."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from tracks_and_trails.ui.add_dialog import AddUrlDialog

_original = AddUrlDialog.__init__


def _with_stray(self, *args, **kwargs):
    _original(self, *args, **kwargs)
    stray = QPushButton("stray", self)
    stray.setObjectName("strayButton")
    stray.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    stray.show()


AddUrlDialog.__init__ = _with_stray
