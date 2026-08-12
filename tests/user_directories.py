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

**What this does not cover, stated rather than implied.** A monkeypatch lives in one interpreter,
so a test that *spawns* a process — a worker under `spawn`, or `python -m tracks_and_trails` —
gives that child the real directories unless it passes explicit paths. `tests/ui/test_app_launch.py`
already does exactly that, by setting `XDG_*` for the child it launches; this module is the
in-process half and does not replace it.
"""

from __future__ import annotations

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

    def undo() -> None:
        for target, name, original in reversed(saved):
            setattr(target, name, original)

    return undo
