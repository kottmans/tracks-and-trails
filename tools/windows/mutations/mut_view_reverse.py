"""The mutation T060-R2 asked for, run on Windows to confirm what was measured offscreen.

Reverses what setTabOrder DELIVERS while leaving focus_chain()'s declaration untouched.

EXPECTED TO BE KILLED since `T-084` (`T-331`, Windows run 2026-09-13). This said it would survive
because no state of the progress view offered more than two reachable controls, and a two-element
cycle is its own reverse. `T-084` added the diagnostics box to every state, so a failed, retryable
job now offers three — error message, retry, diagnostics — and reversing three is observable. The
run on `STARBASE` reported **KILLED (unexpected)**: the test was right, the expectation was a fact
about a view that no longer exists. A running job still offers two, which is why only the failed
state's case fails.
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
