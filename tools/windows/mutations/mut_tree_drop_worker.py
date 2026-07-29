"""`T072-R1`'s second mutation: the worker is dropped from the set the kill is handed.

`capture_the_doomed_tree()` returns everything except the worker. The application and the launcher
still die; the worker is never asked to.

**What must catch it is `the_workers_that_must_die()`**, which the test obtains separately and
this plugin does not touch. That separation is the whole point of the second round of `T072-R1`:
the first correction asserted against the same list the kill was given, so dropping the worker
from that list also dropped it from the assertion and nothing could ever fail.

**It survives on both platforms, and that is the result rather than a gap** (`T-072`, measured
2026-07-29). On POSIX `kill_the_application()` signals the whole process group, so the worker dies
whether or not it was captured. On Windows the members are killed one at a time — and the worker
*still* dies, because `worker.spawn_session()` runs the `parent-watchdog` thread `ARC-002`
documents, which exits the worker when the application disappears.

So the captured set's completeness is **not** the product invariant, and no platform can gate it
through this test. What prevents orphans is the watchdog; `mut_control_worker_survives` is the
control that shows the assertion can fail at all, by leaving the parent alive so the watchdog
never fires.

*(This file previously said the captured set "has to be complete" on Windows and that the gate
belonged there. The run contradicted it.)*
"""


def pytest_configure(config):
    import sys

    sys.path.insert(0, str(config.rootpath))
    import tests.integration.test_end_to_end as end_to_end

    real_capture = end_to_end.capture_the_doomed_tree

    def drop_the_worker(process, application_pid):
        captured = real_capture(process, application_pid)
        return [victim for victim in captured if victim.pid in (process.pid, application_pid)]

    end_to_end.capture_the_doomed_tree = drop_the_worker
