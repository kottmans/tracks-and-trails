"""POSITIVE CONTROL for the desktop selection, not a mutation.

Changes the main window's title after construction. `test_windows_desktop.py` asks **Windows
itself** what the title is — `GetWindowTextW`, not `windowTitle()`, deliberately, because asking
Qt what Qt set would be circular — and compares it with `APP_NAME`. So this mutation cannot be
passed by that suite however the widgets are arranged.

MUST be reported as killed. If it survives, the plugin mechanism is not taking effect.

**This replaced `mut_control_chain` as the control on 2026-09-11** (`T-331`). That one empties the
dialog's declared focus chain, which leaves Qt's construction order — and the desktop tests write
their expected order out by hand rather than deriving it, so they pass whenever the delivered
order matches, which on this dialog it already does. It was a control that could survive for a
product reason, which is the one thing a control must never do.
"""

from tracks_and_trails.ui.main_window import MainWindow

_original = MainWindow.__init__


def _retitled(self, *args, **kwargs):
    _original(self, *args, **kwargs)
    self.setWindowTitle("T-331 control: this title is wrong on purpose")


MainWindow.__init__ = _retitled
