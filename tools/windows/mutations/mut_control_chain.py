"""POSITIVE CONTROL for the focus mutations, not a mutation.

Empties the dialog's declared focus chain, so `_set_tab_order` places nothing and the dialog
tests cannot possibly pass. It MUST be reported as killed.

If it survives, the plugin mechanism is not taking effect and every other verdict in this run is
meaningless — the distinction between "the mutation survived" and "the mutation never applied",
which no amount of care in reading the numbers can recover after the fact.
"""

from tracks_and_trails.ui.add_dialog import AddUrlDialog


def _nothing(self):
    return []


AddUrlDialog.focus_chain = _nothing
