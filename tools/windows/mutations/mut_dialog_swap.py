"""T-026 mutation class 1: reorder two widgets in the add-URL dialog's declared chain.

**By name, and two that every dialog state offers** (`T-331`, Windows run 2026-09-13). This swapped
indices 3 and 4, under a docstring naming `titleValue` and `uploaderValue` — but the dialog was
rebuilt since (`T-312`), and those indices became `statusMessage` and `presetChoice`. The status
line is `NoFocus` in three of the four states the desktop suite checks, so the swap could not be
observed there, and the run on `STARBASE` reported it **SURVIVED (unexpected)** against a correct
dialog. The mutation had stopped being the mutation its name described.

`urlInput` and `stagingList` are reachable in every state `DIALOG_STATES` lists, so swapping them
changes the delivered order wherever the suite looks. Probe and cancel-probe would not do: they are
never enabled at the same time, and a two-element cycle has no observable orientation (T060-R2).

Applied as a pytest plugin rather than a source edit: a failed run cannot leave a mutated file
behind, and the checkout stays clean the whole time.
"""

from tracks_and_trails.ui.add_dialog import AddUrlDialog

_original = AddUrlDialog.focus_chain


def _swapped(self):
    chain = _original(self)
    names = [widget.objectName() for widget in chain]
    first, second = names.index("urlInput"), names.index("stagingList")
    chain[first], chain[second] = chain[second], chain[first]
    return chain


AddUrlDialog.focus_chain = _swapped
