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
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests import user_directories
from tests.capabilities import ffmpeg, symlinks

__all__ = ["ffmpeg", "symlinks"]


# --- `ai/TESTING.md` §5, which had a rule and no mechanism (`T123-R2`) -------------------------
#
# §5 says tests must not touch the developer's real config, data or cache directories, and that
# `platformdirs` paths are redirected to `tmp_path` **by an autouse fixture**. That fixture did
# not exist. Eight test files arranged their own redirect and everything else went to the real
# machine: one `-n auto tests/unit tests/ui` run left **241 job logs** under the real
# `user_cache_dir`, measured 2026-08-11.
#
# It is here rather than in a suite's own conftest because the rule is every suite's, and because
# a root conftest is the one place that runs before all of them. `tests/user_directories.py` is
# Qt-free and patches only modules already imported, so this file keeps the property its own
# docstring claims.


@pytest.fixture(autouse=True)
def _per_user_directories(tmp_path: Path) -> Iterator[None]:
    """Give this test its own config, data, cache and downloads directories.

    **It does not request `monkeypatch`, and that is load-bearing** — see `redirect`. Requesting it
    from an autouse fixture moves `monkeypatch`'s undo after the teardown of fixtures the test
    declared itself, which broke `test_kill_tree_reports_a_survivor`.
    """
    undo = user_directories.redirect(tmp_path / "platform")
    try:
        yield
    finally:
        undo()


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


# **The pool gates are process-global, and sealing one is permanent** (`T289-R21`). That is correct
# in a running application — shutdown happens once — and it leaks in a suite: a test that composes
# the application and closes it seals the *module's* pool, and every later test in that worker gets
# a pool that refuses work. Nine tests failed that way, all of them passing alone, and the order
# that made them fail was the accident of which worker collected them.
#
# **Replaced around every test rather than fixed where it showed** — `tests/ui/conftest.py` makes
# the same argument about theme dressing, for the same reason: a reset aimed at today's failures
# leaves the next one to be found by accident. The singleton is dropped before each test and the
# original put back after, so no test can leak a sealed pool and none can be affected by one.
#
# The globals are private and reached by name deliberately: an `unseal()` on `SealedPool` would be
# production API that exists only for tests, and it would weaken the one invariant the gate has.
#
# **Two corrections, both `T289-R23`.**
#
# 1. **It imported Qt for every test in the suite.** The first version did
#    `from tracks_and_trails.ui import thumbnails`, unconditionally, from a root `conftest.py` —
#    which is imported before `tests/unit/` too, and both of these modules import `PySide6`. A
#    fixture whose whole purpose is isolation retired this file's stated Qt-free property to get
#    it. `sys.modules` answers the same question without loading anything: a module that was never
#    imported has no singleton to reset, and one imported *during* the test is found at teardown
#    because the dictionary is re-read there rather than remembered.
# 2. **It dropped whatever the test had created without asking whether it was busy.** A
#    `QThreadPool` released with runnables in flight is destroyed by whichever thread collects it,
#    and its destructor waits there — or aborts. That segfaulted this suite once, and the test that
#    caused it had to join its own task to work around a fixture that should have owned this. So a
#    pool created during a test is now sealed and drained here, and a pool that will not drain
#    fails the test that left it rather than crashing an unrelated one later.
_POOL_SINGLETON_MODULES = (
    "tracks_and_trails.downloader.ytdlp_service",
    "tracks_and_trails.ui.thumbnails",
)

#: How long a test's own pool is given to finish before the failure is attributed to it. Generous:
#: the point is to name the test that left work running, not to police how long its work took.
_POOL_TEARDOWN_WAIT_MS = 30_000


@pytest.fixture(autouse=True)
def _pools_are_not_shared_between_tests() -> Iterator[None]:
    before: dict[str, Any] = {}
    for name in _POOL_SINGLETON_MODULES:
        module = sys.modules.get(name)
        if module is None:
            # Not imported yet, so there is no singleton to displace and nothing to import one
            # for. If the test imports it, teardown below finds it.
            continue
        before[name] = module._SHARED_POOL
        module._SHARED_POOL = None
    try:
        yield
    finally:
        for name in _POOL_SINGLETON_MODULES:
            module = sys.modules.get(name)
            if module is None:
                continue
            created = module._SHARED_POOL
            # **Drained first, restored second, and the order is the whole of it** (`T289-R23`,
            # third pass). Restoring the singleton before the wait leaves the module global holding
            # the *previous* pool — usually `None` — for the entire length of the drain, and a task
            # still running asks `pool()`, not the object the fixture happens to be holding. So it
            # was handed a freshly built replacement whose `cancelled` is false: the gate being
            # drained reported `cancelled=True` while the task on it saw `False`, went on working,
            # and left an uncaptured second pool behind. Sealing a pool nothing can reach is not
            # cancelling anything.
            if created is not None:
                # Sealed as well as waited, so anything still queued declines rather than starting
                # a fresh piece of work into a pool that is being discarded.
                created.seal()
                drained = created.wait_bounded(_POOL_TEARDOWN_WAIT_MS)
            else:
                drained = True
            # `before` may have no entry: the module was first imported by the test itself, and
            # then the pool to put back is the one that was there before it existed, which is none.
            # Restored before the raise below, so a test that fails here still leaves the next one
            # a clean module.
            module._SHARED_POOL = before.get(name)
            if not drained:
                raise RuntimeError(
                    f"{name} was left with pool work still running after "
                    f"{_POOL_TEARDOWN_WAIT_MS} ms. Dropping a busy QThreadPool destroys it on "
                    "whichever thread collects it, which is a segfault somewhere else; release "
                    "whatever this test is blocking before it ends."
                )
