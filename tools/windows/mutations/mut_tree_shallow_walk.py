"""`T072-R1`'s first mutation: the capture walk finds the application but not the worker.

This is the exact shape that defeated the assertion this mutation exists to gate. The previous
`kill_the_application()` walked from the pid `Popen` returned and asserted `len(doomed) > 1` —
but under the Windows venv shape the launcher plus the application interpreter already make that
two, so the *worker* could be absent and the assertion still passed. Codex reproduced it: the
helper returned successfully and the omitted worker went on downloading.

`capture_the_doomed_tree` now walks from the application's own reported pid and asserts it has
descendants, so blinding that walk **must** be reported as killed.

Blinding is scoped to the capture's own stack frame on purpose. Making `children()` return
nothing everywhere would break unrelated helpers and prove nothing about this assertion — the
mutation has to be the specific thing the assertion claims to catch.
"""

import inspect

import psutil

_real_children = psutil.Process.children


def _blind_inside_the_capture(self, recursive=False):
    for frame in inspect.stack():
        if frame.function == "capture_the_doomed_tree":
            return []
    return _real_children(self, recursive=recursive)


psutil.Process.children = _blind_inside_the_capture
