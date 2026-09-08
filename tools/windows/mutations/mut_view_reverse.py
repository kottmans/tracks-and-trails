"""The mutation T060-R2 asked for, run on Windows to confirm what was measured offscreen.

Reverses what setTabOrder DELIVERS while leaving focus_chain()'s declaration untouched.

EXPECTED TO SURVIVE. No state of the progress view offers more than two reachable controls, and
a two-element cycle is its own reverse: from either control, Tab and Backtab both deliver the
other one, from any starting point. Recorded rather than answered with an assertion that appears
to catch it (docs/project/TESTING.md 12).
"""

from itertools import pairwise

from tracks_and_trails.ui.job_detail import JobProgressView

_original = JobProgressView.__init__


def _reversed_delivery(self, *args, **kwargs):
    _original(self, *args, **kwargs)
    chain = list(reversed(self.focus_chain()))
    for earlier, later in pairwise(chain):
        self.setTabOrder(earlier, later)


JobProgressView.__init__ = _reversed_delivery
