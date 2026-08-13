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
from pathlib import Path

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
