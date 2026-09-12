"""Does the declared focus chain actually deliver the order, or does construction order?

Empties the dialog's declared chain, so `_set_tab_order` makes no `setTabOrder` calls at all and
Qt's **construction order** stands.

**This was the positive control until 2026-09-11, and it was never a valid one** (`T-331`). Its
previous text said it *"MUST be reported as killed"* and that survival meant the plugin mechanism
had failed and every other verdict was meaningless. Both are wrong. Run on `STARBASE` it survived
the desktop selection while three other mutations were killed in the same table — so the mechanism
plainly applied — and the reason it survived is a fact about the product: construction order on
this dialog already matches the declaration, and `test_windows_desktop.py` writes its expected
order out by hand rather than deriving it from `focus_chain()`.

So it is a **mutation**, not a control, and it is run against the selection that detects it:
measured on Linux, it fails 4 tests in `test_accessibility.py` and `test_add_dialog.py`, none of
which carries the `windows_desktop` marker. `mut_control_title` is the control now.
"""

from tracks_and_trails.ui.add_dialog import AddUrlDialog


def _nothing(self):
    return []


AddUrlDialog.focus_chain = _nothing
