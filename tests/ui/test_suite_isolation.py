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
