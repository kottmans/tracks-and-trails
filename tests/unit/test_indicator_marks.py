"""The marks the theme draws in its check boxes exist, and ship (`T-327` session, 2026-09-13).

**Nothing else would notice either going missing.** Qt draws an indicator whose `image:` cannot be
loaded as a box with nothing in it, so a ticked option would look unticked and every test that
reads the sheet as text would still pass.
"""

import re
from pathlib import Path
from typing import Final

import pytest

from tracks_and_trails.ui import theme

REPOSITORY: Final = Path(__file__).resolve().parents[2]
SPEC: Final = REPOSITORY / "packaging" / "tracks-and-trails.spec"


@pytest.mark.parametrize("chosen", list(theme.THEMES.values()), ids=lambda t: t.name)
def test_every_mark_the_sheet_names_is_a_file(chosen: theme.Theme) -> None:
    named = re.findall(r'image:\s*url\("([^"]+)"\)', theme.stylesheet(chosen))
    assert len(named) == 4, f"expected a tick, a dash and each disabled, found {named}"
    for path in named:
        assert Path(path).is_file(), f"the {chosen.name} sheet draws {path}, which does not exist"
        high = Path(path).with_name(Path(path).stem + "@2x.png")
        assert high.is_file(), f"{path} has no @2x, so a scaled display draws it blurred"


def test_the_build_collects_the_marks() -> None:
    assert 'includes=["resources/indicators/*"]' in SPEC.read_text(encoding="utf-8"), (
        "the PyInstaller spec no longer collects resources/indicators, so the frozen build's "
        "ticked boxes would be drawn empty"
    )
