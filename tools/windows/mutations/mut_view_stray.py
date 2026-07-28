"""T-026 mutation class 2, the progress view's half."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from tracks_and_trails.ui.job_detail import JobProgressView

_original = JobProgressView.__init__


def _with_stray(self, *args, **kwargs):
    _original(self, *args, **kwargs)
    stray = QPushButton("stray", self)
    stray.setObjectName("strayViewButton")
    stray.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    stray.show()


JobProgressView.__init__ = _with_stray
