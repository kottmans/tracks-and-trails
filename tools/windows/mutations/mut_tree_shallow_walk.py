"""`T072-R1`'s first mutation: the capture walks only direct children.

This is the shape that defeated the original assertion. The old code walked from the pid `Popen`
returned — the venv launcher — so `recursive=True` reached the application *and* the worker, while
`recursive=False` reached only the application. Two entries either way, which is why
`len(doomed) > 1` could not tell them apart.

**Its verdict now depends on how deep the tree actually is, and that is a measurement rather than
a defect.** The capture walks from the application, whose direct children already include the
worker, so making the walk shallow changes nothing unless the worker has spawned a child of its
own — ffmpeg, on a download that needs merging. On a progressive download it does not, so this
mutation is expected to **survive**, for the same reason `T060-R2`'s reversal survives: the thing
it removes is not observable in the state the test creates.

An earlier version of this plugin returned `[]` instead. That killed cleanly and proved nothing:
an empty walk is not the fault anyone found, and reporting it as a kill would have been the
"mutation that never applied" failure `mut_control_chain` exists to prevent.
"""

import inspect

import psutil

_real_children = psutil.Process.children


def _shallow_inside_the_capture(self, recursive=False):
    for frame in inspect.stack():
        if frame.function in ("capture_the_doomed_tree", "the_workers_that_must_die"):
            return _real_children(self, recursive=False)
    return _real_children(self, recursive=recursive)


psutil.Process.children = _shallow_inside_the_capture
