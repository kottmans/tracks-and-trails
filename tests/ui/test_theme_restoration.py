"""The two fields `_undressed_afterwards` restores that nothing proved (`T-229`, `T225-R1`).

`T-225` fixed a real leak: a test dressed the shared `QApplication` and left it dressed, and two
later tests asserted behaviour an undressed application has. Its regression
(`tests/ui/test_suite_isolation.py`) proves the **style sheet** half, because that is the half the
observed failures turned on.

**The palette and `theme._applied` are restored by the same fixture and were asserted by nothing.**
`tests/ui/conftest.py` says so in terms — *"a leak with no test on it rather than a leak that cannot
happen"* — and `T225-R1` asked for the gap to be closed rather than described. Removing either
restoration left the whole suite green.

**Why the pair is here rather than one test.** The defect exists *between* tests: the fixture runs
in the gap. A single test cannot observe it, and neither can a test that dresses and checks itself.
So one test dresses and the next reads, and `test_suite_isolation.py` runs the two **in that order
in a subprocess** — the order is what gives them their power, and the default `-n auto`
distribution scatters individual tests across workers.

**Each test is still honest on its own.** The bare dressing is captured by a module-scoped fixture
before either runs, so the reader passes whichever order it is given; what the pinned order adds is
the ability to *fail*. A test that only passes when its neighbour ran first would be a test with a
hidden dependency, which is the defect this file exists about.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from tracks_and_trails.ui import theme


@pytest.fixture(scope="module")
def bare(qapp: QApplication) -> Iterator[tuple[str, QPalette, theme.Theme]]:
    """What the application looked like before either test in this module ran.

    Module-scoped on purpose: captured once, before the dresser, so the reader compares against a
    state no test in this file has touched.
    """
    yield qapp.styleSheet(), qapp.palette(), theme.applied()


def test_a_theme_is_applied_and_deliberately_not_cleaned_up(
    qapp: QApplication, bare: tuple[str, QPalette, theme.Theme]
) -> None:
    """Dress the shared application and leave it dressed. **The fixture is the cleanup.**

    This is the shape of the test that caused `T-225`: it does its job and returns, and something
    else is responsible for putting the application back. If that something stops working, the next
    test is the one that fails — which is exactly what this file is for.
    """
    theme.apply(qapp, theme.DARK)

    assert theme.applied() == theme.DARK, "the theme did not apply, so nothing is left to restore"
    assert qapp.palette() != bare[1] or qapp.styleSheet() != bare[0], (
        "applying a theme changed neither the palette nor the sheet, so this test dresses nothing "
        "and the reader below would pass against a broken fixture"
    )


def test_the_palette_and_the_applied_theme_came_back(
    qapp: QApplication, bare: tuple[str, QPalette, theme.Theme]
) -> None:
    """**All three fields**, and the two that matter here are the palette and `_applied`.

    Run after the dresser (see `test_suite_isolation.py`), this fails if `_undressed_afterwards`
    stops restoring either — which is the evidence `T225-R1` asked for and the suite did not have.

    The palette is compared with `QPalette.__eq__` rather than `cacheKey()`, for the reason
    `_dressing` gives: a restored palette is equal to the saved one and does not get its cache key
    back, so a key comparison reports a leak on every correct cleanup.
    """
    sheet, palette, applied = bare

    assert qapp.palette() == palette, (
        "the palette was not restored, so a test that reads a colour now sees the previous test's "
        "theme. tests/ui/conftest.py restores it; something stopped."
    )
    assert theme.applied() == applied, (
        f"theme.applied() is {theme.applied()!r} for the next test rather than {applied!r} — "
        "row_delegate reads it while painting, so a leak changes what a later test is shown"
    )
    assert qapp.styleSheet() == sheet, "the style sheet was not restored (T-225's original leak)"
