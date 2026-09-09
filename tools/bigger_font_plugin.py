"""A pytest plugin that runs the UI suite at a larger application font.

**Nothing in CI asks what happens when the font grows**, and on 2026-09-08 that turned into two
red jobs the moment Linux moved to `ubuntu-latest`, whose default font is wider than Fedora's.
The two assertions involved were repaired by measuring rather than by loosening — see
`tools/dialog_width_floor_probe.py` — and this plugin is the lever that made the repair checkable
on a machine where the suite was green.

    PYTHONPATH=tools python -m pytest -q -p bigger_font_plugin tests/ui

**One point is a deliberately harsher perturbation than any real platform difference.** Fedora to
Ubuntu broke two tests; one point breaks about forty-five. So this measures how tightly the suite
is coupled to font metrics, and it does **not** predict what a given distribution will do. Read a
failure here as a question — *is the product wrong at this size, or is the assertion?* — and not
as a defect.

**It is not wired into CI, and that is deliberate.** Gating on it would commit the project to a
standard before anyone has established the product meets it, and a board that is permanently red
for a known reason hides the next real failure — which is the reasoning that removed the
`STARBASE orphans` job on 2026-09-03.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication

#: Points added to the application font. One is enough to move a layout well past the difference
#: between two distributions' default fonts.
ENLARGE_BY = 1


@pytest.fixture(autouse=True)
def _bigger_font() -> Iterator[None]:
    """Enlarge the application font for the duration of each test.

    Applied per test rather than once per session because `QApplication` is created lazily by the
    Qt fixtures: a session hook would run before there is an application to set a font on.
    """
    app = QApplication.instance()
    if app is None:
        yield
        return
    original = app.font()
    enlarged = app.font()
    enlarged.setPointSize(original.pointSize() + ENLARGE_BY)
    app.setFont(enlarged)
    try:
        yield
    finally:
        app.setFont(original)
