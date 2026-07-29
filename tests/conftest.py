"""Fixtures every suite can use, and nothing that costs anything to import (`T-070`).

**Deliberately Qt-free.** `tests/unit/` runs headless and without Qt on purpose (`ai/TESTING.md`
§1), and a root `conftest.py` is imported before every suite — putting a Qt import here would
quietly retire that property. `tests/ui/conftest.py`, `tests/integration/conftest.py` and
`tests/network/conftest.py` each keep their own Qt setup for that reason, duplicated rather than
hoisted.

What belongs here is the opposite kind of thing: a question about the machine that any suite
might need to ask. `tests/capabilities.py` holds the answers; this makes its fixtures visible,
because pytest discovers fixtures from `conftest.py` and plugins, not from an ordinary module.
"""

import os
import sys
from pathlib import Path

from tests.capabilities import ffmpeg, symlinks

__all__ = ["ffmpeg", "symlinks"]

# --- Qt needs to be told where Windows keeps its fonts (`T-068`) -------------------------------
#
# Measured 2026-07-28 on a Windows 10 machine that is not a CI runner: under
# `QT_QPA_PLATFORM=offscreen`, `QFontDatabase.families()` returns **zero** families and the
# default family falls back to "Sans Serif". Qt announces it on stderr — "Cannot find font
# directory <prefix>/PySide6/lib/fonts. Note that Qt no longer ships fonts" — which is what
# `test_application_launches_and_exits_cleanly` caught, since that test asserts a clean run
# writes nothing there.
#
# The warning is the symptom and the empty database is the defect. The **whole offscreen UI
# suite** runs on that machine with no fonts at all, so every assertion about a widget's size,
# about elision, or about anything else derived from font metrics is measured against nothing.
# It passes, which is the worrying part: a suite that agrees with itself while measuring an
# empty font set is the shape `ai/TESTING.md` §13 exists to catch.
#
# So this is fixed in the environment rather than allowlisted in the assertion. Pointing Qt at
# the directory Windows actually keeps its fonts in restores a populated database, verified by
# the same `families()` count going from 0 to a real list.
#
# `setdefault`, so an explicit value from a caller still wins. Windows only — elsewhere Qt finds
# fonts through fontconfig and the variable is meaningless.
#
# **Not yet verified on a CI runner.** The runners do not show the warning, so their offscreen
# Qt evidently finds fonts by some other route; whether this variable changes anything there is
# unknown until a run happens, and GitHub Actions is out of quota. If their font database is
# already populated, `QT_QPA_FONTDIR` is simply ignored.
if sys.platform == "win32":
    _windows = Path(os.environ.get("WINDIR", r"C:\Windows"))
    os.environ.setdefault("QT_QPA_FONTDIR", str(_windows / "Fonts"))
