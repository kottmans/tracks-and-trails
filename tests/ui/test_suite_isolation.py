"""The UI suite passes in an order the alphabet did not choose (`T-225`).

**Why this file exists at all.** `T-225` was two `tests/ui/test_add_dialog.py` tests that failed
when `tests/ui/test_row_delegate.py` ran before them and passed when it did not. Nothing was wrong
with the product: one test dressed the shared `QApplication` in a theme and left it dressed, and
the two that failed assert behaviour an undressed application has. **The suite was green only
because pytest collects `add_dialog` before `row_delegate`** — an accident of the alphabet, and one
a file rename, `-p randomly`, an `-n auto` shard boundary or a developer running one file to save
time would have ended.

`tests/ui/conftest.py`'s `_undressed_afterwards` is the fix. This is the test that fails if it is
removed, because the property it restores is otherwise asserted by nothing: every other test in the
suite passes either way, in the order the alphabet happens to give them.

**Run as a subprocess, and the reason is the point.** The defect exists only *between* tests in one
process, so a test observing it from inside that same process would be observing something else.
`pytest` is invoked on the three node ids that reproduced it — the one test that dresses the
application, and the two that failed — which cost **about four seconds** against the four minutes
the two whole files take.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QRunnable

from tests import conftest as root_conftest
from tracks_and_trails.ui import thumbnails

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

    from tracks_and_trails.downloader.pools import SealedPool

#: The one test in `tests/ui/test_row_delegate.py` that dresses the shared application, and the two
#: in `tests/ui/test_add_dialog.py` that `T-225` recorded failing after it.
#:
#: **Node ids rather than whole files.** The reproduction does not need the other 216 tests, and a
#: four-minute regression is one nobody runs.
DRESSES_THE_APPLICATION = (
    "tests/ui/test_row_delegate.py::test_an_abandoned_block_is_not_drawn_like_a_finished_one"
)
ASSERT_AN_UNDRESSED_APPLICATION = (
    "tests/ui/test_add_dialog.py::test_an_open_playlist_shows_entries_and_a_way_back",
    "tests/ui/test_add_dialog.py::test_the_menu_key_reaches_the_current_rows_menu",
)


def test_dressing_the_application_does_not_fail_the_tests_that_run_next() -> None:
    """The order `T-225` reported, asserted rather than inherited from the alphabet.

    **Verified to fail without the fix**: with `_undressed_afterwards` removed from
    `tests/ui/conftest.py` this exits 1, with exactly the two failures `T-225` filed.

    The second assertion is not decoration. A renamed node id would make the subprocess collect
    nothing and pass, so the count is checked too — a guard that silently stops guarding is
    `T214-R1`'s finding, and `T-096` exists because of the same shape one file over.
    """
    node_ids = (DRESSES_THE_APPLICATION, *ASSERT_AN_UNDRESSED_APPLICATION)
    # `no:randomly` so this reproduction keeps its order even if the suite later grows a
    # randomiser — the order *is* what it asserts. Harmless when no such plugin is installed.
    finished = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:randomly", "-q", *node_ids],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
        timeout=600,
    )

    assert finished.returncode == 0, (
        "a test that dresses the application still fails the tests collected after it — the leak "
        f"`T-225` fixed is back.\n\n{finished.stdout}\n{finished.stderr}"
    )
    assert "3 passed" in finished.stdout, (
        "the reproduction did not run all three tests, so it no longer asserts the order `T-225` "
        f"reported.\n\n{finished.stdout}\n{finished.stderr}"
    )


# --- T-229: the two fields the regression above does not exercise ------------------------------

#: The pair in `tests/ui/test_theme_restoration.py`, in the order that gives them their power.
#:
#: **Its own file, and node ids again.** The reader passes in any order — its baseline is captured
#: by a module-scoped fixture — so what this pins is the order in which it can *fail*. The default
#: `-n auto` distribution hands individual tests to whichever worker is free, which would separate
#: them.
RESTORATION_PAIR = (
    "tests/ui/test_theme_restoration.py::test_a_theme_is_applied_and_deliberately_not_cleaned_up",
    "tests/ui/test_theme_restoration.py::test_the_palette_and_the_applied_theme_came_back",
)


def test_the_palette_and_the_applied_theme_are_restored_between_tests() -> None:
    """`T225-R1`: the sheet was proved and the other two restored fields were not.

    `tests/ui/conftest.py` restores three things and the regression above turns on one of them.
    The other two — the palette, and the `theme._applied` module global `row_delegate` reads while
    painting — could be deleted from the fixture with **the whole suite still green**. Its own
    comment says so, and says it is a record rather than a defence.

    **Verified by mutation, both fields separately** (2026-08-12): removing the palette
    restoration fails this on the palette assertion; removing the `theme._applied` restoration
    fails it on that one. Both, every time.

    **What the rest of the suite does under those mutants is the more interesting number, and it is
    not a clean one.** With `theme._applied` unrestored, `tests/unit` + `tests/ui` at `-n auto` is
    **green** — 2722 passed. With the *palette* unrestored it was green in **three runs of four**,
    and in the fourth something else failed. Which is this file's whole subject seen from the other
    side: whether a leak is noticed depends on which worker collects which test, so a green suite is
    evidence about the distribution rather than about the fixture. **That is why this regression
    pins the order in a subprocess instead of trusting the suite to notice.**
    """
    finished = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:randomly", "-q", *RESTORATION_PAIR],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
        timeout=600,
    )

    assert finished.returncode == 0, (
        "a dressed application reached the next test with its palette or applied theme still on "
        f"it.\n\n{finished.stdout}\n{finished.stderr}"
    )
    assert "2 passed" in finished.stdout, (
        "the pair did not both run, so this no longer asserts anything about the order between "
        f"them.\n\n{finished.stdout}\n{finished.stderr}"
    )


# --- T-238: a leaked view fails its own test, rather than a later one -------------------------

#: The deliberately bad test. **Not collected by the suite** — `python_files` is `test_*.py` and
#: this file is not — so it runs only when named directly, which is what the regression below does.
LEAKS_A_VIEW = "tests/ui/_leaks_a_view.py::test_leaks_a_view"


def test_a_test_that_leaks_a_view_is_the_test_that_fails() -> None:
    """`T-238`'s guard, proved by leaking a view rather than by reading the check.

    **The crash this exists for named the wrong test.** An `-n auto` worker died in
    `~QAbstractItemView` reached from `_Py_HandlePending`, inside a test whose file constructs no
    view at all: a deferred deletion executing at an arbitrary bytecode boundary. Sixty runs did
    not reproduce it, so what is asserted here is not the segfault — it is that a leak now fails
    **where it happens**, which is `ai/TESTING.md` §13's rule and the maintainer's reason for
    authorising the guard.

    **The subprocess runs the real wiring**, not a copy of it: `_leaks_a_view.py` sits under
    `tests/ui/`, so `conftest.py`'s autouse fixture, the boundary drain and the orphan check all
    apply in the order the conftest gives them.

    **Two assertions, because a guard that silently stops guarding is the failure mode this file
    already exists for** (`T-225`, `T214-R1`): the run must fail, *and* it must fail with the
    orphan message. A renamed node id, a moved fixture, or a guard reduced to a no-op would
    otherwise leave a collection error looking like success.
    """
    finished = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:randomly", "-q", LEAKS_A_VIEW],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
        timeout=600,
    )

    assert finished.returncode != 0, (
        "a test that leaves an item view alive with no owner passed. The guard that names the "
        f"leaking test is gone, so the next leak is found wherever it lands.\n\n{finished.stdout}"
    )
    assert "alive with no parent" in finished.stdout, (
        "the run failed for some other reason than the view leak, so this asserts nothing about "
        f"the guard.\n\n{finished.stdout}\n{finished.stderr}"
    )


#: `T289-R23`'s deliberate violation. A test that ends with work still running on a real pool.
LEAVES_A_POOL_THREAD_RUNNING = (
    "tests/ui/_leaves_a_pool_thread_running.py::test_leaves_a_pool_thread_running"
)


def test_a_test_that_leaves_a_pool_thread_running_is_the_test_that_fails() -> None:
    """The root fixture drains what a test created before it drops it, and says who left it.

    **The fixture used not to ask.** It replaced both pool singletons around every test and
    discarded whatever the test had made, busy or not — and a `QThreadPool` released with runnables
    in flight is destroyed by whichever thread collects it, where its destructor waits or aborts.
    That segfaulted this suite once inside a test that constructs no pool at all, which is
    `ai/TESTING.md` §13's shape exactly: the useful signal is the one at the cause.

    **Two assertions, for the reason the view guard gives.** The run must fail, *and* it must fail
    with this fixture's message — a renamed node id or a fixture reduced to a no-op would otherwise
    leave a collection error looking like a caught leak.
    """
    finished = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:randomly", "-q", LEAVES_A_POOL_THREAD_RUNNING],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
        timeout=600,
    )

    assert finished.returncode != 0, (
        "a test that ended with a pool thread still running passed. The fixture is dropping busy "
        f"thread pools again, so the next segfault lands in somebody else's test.\n\n"
        f"{finished.stdout}"
    )
    assert "left with pool work still running" in finished.stdout, (
        "the run failed for some other reason than the undrained pool, so this asserts nothing "
        f"about the fixture.\n\n{finished.stdout}\n{finished.stderr}"
    )


#: `T-289`'s deliberate violation. A Python-subclass widget, unparented, held only by a cycle.
LEAKS_A_COLLECTABLE_WIDGET = (
    "tests/ui/_leaks_a_collectable_widget.py::test_leaks_a_collectable_widget"
)


def test_a_test_that_leaves_a_collectable_widget_is_the_test_that_fails() -> None:
    """`T-289`'s guard, proved by producing the state rather than by reading the check.

    **The crash this exists for was a double free, and it named no test at all.** A pool thread ran
    `gc_collect_main` → `~QWidget` while the GUI thread was inside a deletion for the same graph.
    Nothing scheduled it: the collector runs wherever an allocation threshold trips, which is why
    three days of the entry could not say which widget tree was involved. What the guard asserts is
    therefore not the abort — it is the **state** that makes the abort possible, failing at the test
    that produced it.

    **The subject is a Python subclass, and that is the finding it encodes.** A plain `QWidget` in
    the same cycle is marshalled to the GUI thread and destroys nothing dangerous; the subclass is
    destroyed in place. Every widget this project defines is a subclass, so the leak file's shape is
    the product's shape rather than a synthetic worst case.

    **Two assertions, because a guard that silently stops guarding is this file's own subject**
    (`T-225`, `T214-R1`): the run must fail, *and* it must fail with this guard's message. A renamed
    node id or a check reduced to a no-op would otherwise leave a collection error looking like a
    pass.
    """
    finished = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:randomly", "-q", LEAKS_A_COLLECTABLE_WIDGET],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
        timeout=600,
    )

    assert finished.returncode != 0, (
        "a test that left a Python-owned widget reachable only through a cycle passed. The guard "
        "that names it is gone, so the next one is found by a pool thread instead — which is "
        f"T-289's double free.\n\n{finished.stdout}"
    )
    assert "owned by Python and reachable only through a cycle" in finished.stdout, (
        "the run failed for some other reason than the collectable widget, so this asserts nothing "
        f"about the guard.\n\n{finished.stdout}\n{finished.stderr}"
    )


#: `T289-R2`'s bypass: the same violation, collected inside the test so the evidence is gone.
COLLECTS_BEFORE_TEARDOWN = (
    "tests/ui/_collects_before_teardown.py::test_collects_the_dangerous_cycle_before_teardown"
)

#: `T289-R4`'s bypass: the same violation under a **module-level** exemption marker.
MARKS_A_SIBLING_EXEMPT = (
    "tests/ui/_marks_a_sibling_exempt.py::test_a_marked_sibling_still_may_not_leave_one"
)


def test_collecting_the_cycle_inside_the_test_does_not_hide_it() -> None:
    """`T289-R2`: the guard enforces *never left*, not *left at teardown*.

    **The submitted version passed this exact file.** It armed `DEBUG_SAVEALL` at the boundary and
    asked what was garbage then — a question any earlier collection had already answered by freeing
    it. The widget spent the test in the forbidden state, and whether the evidence survived was a
    race the GUI thread happened to win. Automatic collection reaches the same result with nobody
    writing `gc.collect()` at all.

    So the fixture now arms the parking **before** the test and reads it after, and this is the
    regression that says so.
    """
    finished = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:randomly", "-q", COLLECTS_BEFORE_TEARDOWN],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
        timeout=600,
    )

    assert finished.returncode != 0, (
        "a test that produced T-289's state and collected it itself passed. The guard samples "
        f"survivors rather than enforcing the rule.\n\n{finished.stdout}"
    )
    assert "owned by Python and reachable only through a cycle" in finished.stdout, (
        f"the run failed for some other reason, so this asserts nothing.\n\n{finished.stdout}"
    )


def test_the_exemption_marker_cannot_be_claimed_by_a_sibling() -> None:
    """`T289-R4`: the bypass fails closed, including the inherited spellings.

    **`get_closest_marker` is inherited**, so the submitted guard let a class- or module-level
    marker suppress itself for every test underneath — and a real violation in a marked test
    passed. The exemption now requires the allowlisted node id **and** a marker on the function
    itself, and this file claims it the widest way available: `pytestmark` at module level.
    """
    finished = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:randomly", "-q", MARKS_A_SIBLING_EXEMPT],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
        timeout=600,
    )

    assert finished.returncode != 0, (
        "a test that is not T-238's diagnostic claimed its exemption and left a collectable "
        f"widget. The bypass is open to anything that spells the marker.\n\n{finished.stdout}"
    )
    assert "owned by Python and reachable only through a cycle" in finished.stdout, (
        f"the run failed for some other reason, so this asserts nothing.\n\n{finished.stdout}"
    )


# --- T238-R1: the drain half, proved without the orphan assertion ------------------------------

#: The ordered pair in `tests/ui/_carries_a_deletion.py`. **Order is the assertion**: the first
#: leaves two carry-overs behind, the second is what sees them, and running either alone proves
#: nothing.
CARRIES_A_DELETION = (
    "tests/ui/_carries_a_deletion.py::test_leaves_a_deletion_pending",
    "tests/ui/_carries_a_deletion.py::test_the_boundary_left_nothing_behind",
)


def test_a_pending_deletion_does_not_reach_the_next_test() -> None:
    """`T238-R1`: the drain is load-bearing, and this is what fails when it is not.

    **The finding, stated plainly:** the leaked-view regression above proves
    `assert_no_orphaned_views` and nothing else — it still fails with `settle_deferred_deletions`
    reduced to a no-op, so the half that stops an unreachable tree or a posted `DeferredDelete`
    reaching a later test had no evidence of its own. Neither carry-over here is visible to the
    orphan assertion: one is a tree whose view is *parented*, the other a deletion that has been
    posted and not delivered.

    **Mutation-checked statement by statement** (2026-08-13), against this regression:

    | Removed from the conftest or the helper | Result |
    |---|---|
    | the whole `settle_deferred_deletions(qapp)` call | **fails** |
    | `gc.collect()` alone | **fails** |
    | `sendPostedEvents(None, DeferredDelete)` alone | **fails** |
    | `assert_no_orphaned_views(qapp)` alone | passes — and the leaked-view regression fails |

    The last row is the point of having both: each regression fails for exactly one half, so
    neither half can be deleted on the grounds that the suite stays green.
    """
    finished = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:randomly", "-q", *CARRIES_A_DELETION],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
        timeout=600,
    )

    assert finished.returncode == 0, (
        "a widget tree or a posted deletion from one test was still alive at the start of the "
        f"next. The boundary drain is gone, so T-238's carry-over is back.\n\n{finished.stdout}"
    )
    assert "2 passed" in finished.stdout, (
        "the ordered pair did not both run, so this asserts nothing about what one test leaves "
        f"for the next.\n\n{finished.stdout}\n{finished.stderr}"
    )


# --- `T289-R23`: sealing a pool nothing can reach cancels nothing ------------------------------


class _WatchesForCancellation(QRunnable):
    """A task that asks `pool()` — as every real task does — whether it should stop.

    **`pool()` and not a captured reference, because that is the finding.** A running task reaches
    its gate through the module's accessor, so what it observes is whatever the module global holds
    at that moment. A teardown that restores the previous singleton before draining hands it a
    freshly built replacement, whose `cancelled` is false.
    """

    def __init__(self, gate: SealedPool, saw: list[tuple[str, bool]]) -> None:
        super().__init__()
        self.started = threading.Event()
        self._gate = gate
        self._saw = saw

    def run(self) -> None:
        self.started.set()
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            reached = thumbnails.pool()
            if reached.cancelled:
                self._saw.append(("cancelled", reached is self._gate))
                return
            time.sleep(0.005)
        self._saw.append(("never told to stop", thumbnails.pool() is self._gate))


def test_a_task_still_running_at_teardown_is_the_one_that_is_cancelled(
    qapp: QApplication,
) -> None:
    """The fixture must drain the pool it created **before** it puts the previous one back.

    **The order was wrong and the symptom was silent** (`T289-R23`, third pass): the singleton was
    restored first, so for the whole length of the drain the module global held the *previous* pool
    — `None`, in a suite — and a task still running asked `pool()` and was handed a freshly built
    replacement. The reviewer measured the gate reporting `cancelled=True` while the task on it saw
    `False`; it went on working, and the replacement was left behind uncaptured.

    **The fixture is driven directly rather than through a second test**, because the thing being
    asserted happens *inside* its teardown: a test observing it from its own body would be
    observing a moment that has not arrived, and one observing it from the next test would need an
    ordering `-n auto` does not give. The generator is the fixture, so stepping it is the real
    thing and not a copy of it.
    """
    saw: list[tuple[str, bool]] = []
    step = root_conftest._pools_are_not_shared_between_tests.__wrapped__()
    next(step)
    try:
        gate = thumbnails.pool()
        watcher = _WatchesForCancellation(gate, saw)
        assert gate.start(watcher), "the fresh pool refused the task"
        assert watcher.started.wait(timeout=10), "the task never began"
    finally:
        next(step, None)  # the teardown under test: seal, drain, then restore

    assert saw == [("cancelled", True)], (
        "the task running at teardown did not see the cancellation of the pool it was running on. "
        "The fixture restored the singleton before draining, so `pool()` handed the task a "
        f"replacement instead of the gate being sealed: {saw}"
    )
    assert thumbnails._SHARED_POOL is None, (
        "the teardown left a pool behind — either the previous singleton was not restored, or a "
        "replacement was built during the drain and never captured"
    )
