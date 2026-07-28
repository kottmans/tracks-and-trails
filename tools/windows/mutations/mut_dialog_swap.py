"""T-026 mutation class 1: reorder two widgets in the add-URL dialog's declared chain.

titleValue and uploaderValue, because both are reachable in EVERY dialog state, so the swap is
observable. probeButton/cancelProbeButton would NOT be: they are never enabled at the same time,
and a two-element cycle has no observable orientation (T060-R2).

Applied as a pytest plugin rather than a source edit: a failed run cannot leave a mutated file
behind, and the checkout stays clean the whole time.
"""

from tracks_and_trails.ui.add_dialog import AddUrlDialog

_original = AddUrlDialog.focus_chain


def _swapped(self):
    chain = _original(self)
    chain[3], chain[4] = chain[4], chain[3]
    return chain


AddUrlDialog.focus_chain = _swapped
