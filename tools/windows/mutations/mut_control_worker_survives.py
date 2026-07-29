"""POSITIVE CONTROL for the process-tree mutations, not a mutation.

Makes `kill_the_application()` do nothing at all, so the worker is still running when the test
asserts it is gone. It MUST be reported as killed.

This exists because both real mutations legitimately survive on POSIX — `mut_tree_shallow_walk`
because the application's direct children already include the worker, `mut_tree_drop_worker`
because `killpg` reaches the whole group regardless of what was captured. Two survivals and no
kills is indistinguishable from an assertion that cannot fail, which is precisely the shape
`T072-R1` found twice: an assertion that reads like a check and is not one.

So this control is what says the independent worker set has teeth. If it survives, nothing else
in this family means anything, and the same reasoning that put `mut_control_chain` first in the
focus driver applies here.
"""


def pytest_configure(config):
    import sys

    sys.path.insert(0, str(config.rootpath))
    import tests.integration.test_end_to_end as end_to_end

    def kill_nothing(process, doomed):
        return None

    end_to_end.kill_the_application = kill_nothing
