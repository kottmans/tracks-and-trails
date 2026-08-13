"""Redirect the per-user directories at every module that binds one (`ai/TESTING.md` §5).

**§5 has required this since it was written and nothing implemented it.** The rule says tests must
not read or write the developer's real config, data or cache directories, and that *"`platformdirs`
paths are redirected to `tmp_path` by an autouse fixture"*. There was no such fixture: eight test
files each arranged their own redirect, and everything they did not cover went to the real machine.
Measured 2026-08-11 (`T123-R2`): one `-n auto tests/unit tests/ui` run left **241 job logs** under
the real `user_cache_dir`, one per job any UI test happened to create.

**Why patching module attributes rather than setting `XDG_*`.** Every consumer binds the function
by name at import — `from platformdirs import user_cache_dir` — so rebinding `platformdirs` alone
would miss all of them. `XDG_*` would miss more: platformdirs only consults those variables on
POSIX, and the Windows job is the one platform this project keeps finding defects on
(`T146-R3`, `T146-R4`). Rebinding the name each module actually calls is the only spelling that
holds on both.

**The spawned half, added by `T-230`.** A monkeypatch lives in one interpreter, so a test that
*spawns* a process — a worker under `spawn`, or `python -m tracks_and_trails` — used to give that
child the real directories. Measured 2026-08-12 with sentinel roots: `tests/integration` left **62**
files under the real `user_cache_dir`, all `cache/tracksandtrails/jobs/*.log`, from nine files that
spawn children.

**A child inherits its parent's environment, so the environment is where that half is fixed** —
once, here, rather than in nine hand-rolled `env=` dictionaries. `redirect()` therefore sets the
variables `platformdirs` consults *as well as* patching the module attributes; the two must agree,
so both point at the same subdirectories of the same root.

**Neither mechanism is sufficient alone, which is the whole reason both are here.** Module patching
does not cross a process boundary. Environment variables do not reach a consumer that bound the
function at import — and `platformdirs` reads `XDG_*` only on POSIX, which is why the Windows
overrides are set too (`T-131` found that the hard way: `XDG_CONFIG_HOME` alone passed on Linux and
failed on the runner).

**What the environment half still cannot do, stated rather than implied:**

- **A child given an explicit `env=` does not inherit anything.** `tests/ui/test_app_launch.py`
  builds its own environment and sets these variables itself; that remains correct and is not
  replaced.
- **Windows collapses the split.** `platformdirs` resolves config, data and cache from
  `LOCAL_APPDATA` there, so the two `WIN_PD_OVERRIDE_*` variables cannot reproduce the
  cache/config/data separation this module gives POSIX. A Windows child gets one root under
  `windows/`, and a test that writes to the wrong directory is visible there as a wrong *file*
  rather than a wrong *path*.
- **Downloads are not covered by an environment variable.** `platformdirs` resolves
  `user_downloads_dir` from `~/.config/user-dirs.dirs` on POSIX, not from `XDG_DOWNLOAD_DIR`, so a
  spawned child asking for the downloads directory is still answered by the real machine. Nothing
  in `src/` asks a *child* for it — `app.py` is the only consumer and it runs in the parent — so
  this is recorded rather than worked around.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

import platformdirs

#: Which directory each `platformdirs` function stands for, and therefore which subdirectory of
#: the per-test root it is redirected to. Separate subdirectories rather than one, so a test that
#: writes to the wrong one is visible as a wrong *path* instead of a right-looking file.
_DIRECTORIES = {
    "user_cache_dir": "cache",
    "user_config_dir": "config",
    "user_data_dir": "data",
    "user_downloads_dir": "downloads",
}

#: Every module that binds one of those names, with the name it binds.
#:
#: **A list rather than a scan, and it is checked rather than trusted**:
#: `test_every_platformdirs_consumer_is_redirected` re-derives this from `src/` and fails when a
#: module starts importing one of these and is not added here. A redirect that silently stops
#: covering a consumer is the shape `T214-R1` is about — a guard proved against one spelling.
CONSUMERS: tuple[tuple[str, str], ...] = (
    ("tracks_and_trails.core.paths", "user_cache_dir"),
    ("tracks_and_trails.core.logging", "user_cache_dir"),
    ("tracks_and_trails.core.settings", "user_config_dir"),
    ("tracks_and_trails.persistence.db", "user_data_dir"),
    ("tracks_and_trails.downloader.environment", "user_data_dir"),
    ("tracks_and_trails.app", "user_downloads_dir"),
    ("tracks_and_trails.ui.main_window", "user_config_dir"),
)


#: The environment variables a **spawned child** resolves its directories from, and which
#: subdirectory of the per-test root each stands for (`T-230`).
#:
#: `XDG_*` is the POSIX half. `WIN_PD_OVERRIDE_*` is `platformdirs`' documented escape hatch on
#: Windows, where folders come from `SHGetKnownFolderPath` through `ctypes` and setting `APPDATA`
#: does nothing — `T-131` established that, and `tests/ui/test_app_launch.py` has carried the pair
#: since. Both sets are exported on both platforms: the one that does not apply is inert, and a
#: conditional here would be a second thing to keep true.
_CHILD_ENVIRONMENT = {
    "XDG_CACHE_HOME": "cache",
    "XDG_CONFIG_HOME": "config",
    "XDG_DATA_HOME": "data",
    # One root, because Windows has one. See the module docstring.
    "WIN_PD_OVERRIDE_APPDATA": "windows",
    "WIN_PD_OVERRIDE_LOCAL_APPDATA": "windows",
}


def redirect(root: Path) -> Callable[[], None]:
    """Point every per-user directory inside `root`, and return the undo.

    **Deliberately not `monkeypatch`, and this cost a test to learn.** An autouse fixture that
    requests `monkeypatch` makes it a dependency of a fixture set up before the test's own, so
    `monkeypatch`'s undo moves to *after* those fixtures' teardown.
    `test_kill_tree_reports_a_survivor` neuters `kill` and `wait` and relies on them being
    restored before the `reap` fixture tears down; with the ordering moved, the holder survived
    the reap and the test errored. Patching and restoring here keeps `monkeypatch`'s ordering
    exactly as it was.

    **Only modules already imported are patched**, which is what lets the Qt-free root conftest
    cover `ui/main_window.py` without importing Qt: a test module is imported at collection, so by
    the time this runs, whatever the test needs is in `sys.modules` and whatever it does not need
    is absent and irrelevant. `platformdirs` itself is patched too, so a module imported *later*
    binds the redirected function rather than the real one.
    """
    saved: list[tuple[object, str, object]] = []
    saved_environment: list[tuple[str, str | None]] = []

    def patch(target: object, name: str, value: object) -> None:
        saved.append((target, name, getattr(target, name)))
        setattr(target, name, value)

    for name, subdirectory in _DIRECTORIES.items():
        base = root / subdirectory

        def answer(appname: str | None = None, *_: object, _base: Path = base, **__: object) -> str:
            # The real functions append the application slug when given one, and callers rely on
            # that shape — `cache_directory()` is documented as `user_cache_dir/tracksandtrails`.
            return str(_base / appname if appname else _base)

        patch(platformdirs, name, answer)

    for module_name, function_name in CONSUMERS:
        module = sys.modules.get(module_name)
        if module is None:
            continue
        # **A function-local import has no module attribute to patch, and needs none.**
        # `app.py` does its `from platformdirs import user_downloads_dir` inside the function
        # that uses it, so the name is looked up on `platformdirs` at *call* time and the patch
        # above already governs it. Patching unconditionally raised `AttributeError` and errored
        # 518 tests; creating the attribute instead would leave a name nothing reads.
        if hasattr(module, function_name):
            patch(module, function_name, getattr(platformdirs, function_name))

    # **The spawned half** (`T-230`). A child inherits this, and nothing else in this function
    # crosses a process boundary. Set after the in-process patching so both halves describe the
    # same root, and restored by the same `undo` so a test that reads the environment sees exactly
    # what it saw before.
    for variable, subdirectory in _CHILD_ENVIRONMENT.items():
        saved_environment.append((variable, os.environ.get(variable)))
        os.environ[variable] = str(root / subdirectory)

    def undo() -> None:
        for target, name, original in reversed(saved):
            setattr(target, name, original)
        for variable, original_value in reversed(saved_environment):
            if original_value is None:
                os.environ.pop(variable, None)
            else:
                os.environ[variable] = original_value

    return undo
