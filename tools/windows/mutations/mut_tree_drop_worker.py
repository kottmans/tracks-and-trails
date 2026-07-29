"""`T072-R1`'s second mutation: the worker is captured, then dropped before the kill.

The walk succeeds — so `capture_the_doomed_tree`'s descendants assertion is satisfied — and the
worker is then removed from the set that gets killed. What must catch it is the *other* half of
the correction, `assert not alive`, because the dropped worker is still running when
`wait_procs` reports.

**This mutation is Windows-only in the meaningful sense.** On POSIX it survives by design and its
survival is not a finding: `kill_the_application()` there sends `SIGKILL` to the whole process
group, so the worker dies whether or not it was in the captured set. Measured on Linux, this
mutation passes. Windows has no process groups and kills the captured members individually, which
is exactly why the captured set has to be complete there and why this gate belongs on this
machine.
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
