"""POSITIVE CONTROL for the process-tree mutations, not a mutation.

Disables `kill_the_application()` entirely, so a real worker is still downloading when the test
asserts nothing survived. It MUST be reported as killed, and the failure MUST name the **worker's**
pid rather than some other long-lived descendant.

**Two earlier versions of this control were wrong, and both failures are the same shape.** The
first disabled the kill while the clip still ran at 0.05 s per chunk: the whole download finished
in under a second, so the worker exited naturally and the only thing left in the set was
`multiprocessing`'s resource tracker. The control "failed", which looked like proof, while proving
nothing about a worker — a reviewer's mutation that killed the application and the tracker but
deliberately spared the real worker passed in 1.38 seconds. The second patched the media handler
here, which hid the same weakness in the test itself rather than fixing it.

Both are gone: `the_workers_that_must_die()` now excludes the tracker, and the test paces its own
clip so a survivor is still running when it looks. This control therefore needs to do nothing but
skip the kill.

It exists because both real mutations legitimately survive on POSIX. Two survivals and no kills is
indistinguishable from an assertion that cannot fail — the exact shape `T072-R1` found three
times.
"""


def pytest_configure(config):
    import sys

    sys.path.insert(0, str(config.rootpath))
    import tests.integration.test_end_to_end as end_to_end

    def kill_nothing(process, doomed):
        return None

    end_to_end.kill_the_application = kill_nothing
