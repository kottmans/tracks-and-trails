"""The seams `T-013` promises are real, read from the source rather than from behaviour.

One of the task's acceptance criteria is about what the manager may *depend on*, and it cannot
be observed by running it: a manager that imported `persistence` directly would pass every
behavioural test in `tests/integration/test_manager.py`, because those hand it a fake and never
ask where the type came from. So this reads the modules statically, the way
`tests/unit/test_layering.py` reads the layer boundaries and for the same reason — the
dependency erodes silently, and by the time anything fails it is load-bearing.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "tracks_and_trails"

#: The GUI-side modules `T-013` owns.
MODULES = ("downloader/manager.py", "downloader/result_pump.py")

#: What `ARCHITECTURE.md` §3 says the manager is *given* rather than builds. `sqlite3` is listed
#: alongside the package because importing the engine directly is the same dependency wearing a
#: disguise.
#:
#: **`core.settings` is here for `ARC-007`** (`T-097`, from `P2PLAN-R6`). The manager receives the
#: concurrency value and a way to be told it changed; composition and the UI own the TOML file. That
#: rule has no other gate: the layering test permits `downloader/` → `core/`, so a direct settings
#: import was measured passing both analysers. Only the `settings` module is forbidden — the manager
#: goes on importing models, errors, job state and logging from `core/`.
#:
#: Applied to both modules in `MODULES` rather than to `manager.py` alone. Neither is a place a
#: settings file should be read, and one shared list is harder to weaken by accident than a
#: per-module table with a single entry.
FORBIDDEN = (
    "tracks_and_trails.persistence",
    "tracks_and_trails.core.settings",
    "sqlite3",
)


def imported_modules(source: str, filename: str = "<test>") -> set[str]:
    """Every module named by an `import` anywhere in `source`, including inside functions.

    A lazy import is still an import: deferring `from ... import JobRepository` into a method
    would make the dependency invisible at the top of the file and no less real.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(source, filename=filename)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
            # **`from package import submodule` names a module too** (`T-097`). Recording only
            # `node.module` missed it: `from tracks_and_trails.core import settings` looked like an
            # import of `tracks_and_trails.core`, which is permitted, while binding the settings
            # module itself. The same hole let `from tracks_and_trails import persistence` through —
            # the original prohibition, unreachable by its own most natural spelling.
            #
            # `alias.name`, never `alias.asname`: the module path is what was imported, not what it
            # was called locally. `from x import y as z` is still an import of `x.y`.
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def offenders(source: str, filename: str = "<test>") -> set[str]:
    """The forbidden dependencies `source` takes on, submodules included."""
    return {
        name
        for name in imported_modules(source, filename)
        if any(name == forbidden or name.startswith(f"{forbidden}.") for forbidden in FORBIDDEN)
    }


@pytest.mark.parametrize("module", MODULES)
def test_the_manager_never_imports_persistence(module: str) -> None:
    """The injected boundary cannot quietly collapse into a direct dependency (`T-013`).

    `ARCHITECTURE.md` §3 gives `DownloadManager` a repository; the manager takes a protocol and
    `app.py` supplies the concrete one at composition time (`T-036`). A single
    `from ...persistence import JobRepository` — added for a type annotation, say — makes the
    protocol decorative and the unit tests a fiction.
    """
    path = SRC / module
    found = offenders(path.read_text(encoding="utf-8"), module)
    assert not found, (
        f"{module} imports {sorted(found)}. The repository is injected as a protocol, not "
        "imported: see ARCHITECTURE.md §3 and DownloadManager's docstring."
    )


@pytest.mark.parametrize(
    "source",
    [
        "import sqlite3",
        "from tracks_and_trails.persistence.repositories import JobRepository",
        "from tracks_and_trails.persistence import db",
        "import tracks_and_trails.persistence.db",
        "def build():\n    from tracks_and_trails.persistence import db\n",
        # `T-097` / `ARC-007`: every spelling of the settings dependency.
        "from tracks_and_trails.core import settings",
        "from tracks_and_trails.core.settings import concurrency_limit",
        "import tracks_and_trails.core.settings",
        "from tracks_and_trails.core import settings as s",
        "def read():\n    from tracks_and_trails.core import settings\n",
        # The hole `T-097` found while adding the above: the persistence prohibition's own most
        # natural spelling was unreachable.
        "from tracks_and_trails import persistence",
    ],
)
def test_the_check_above_can_actually_fail(source: str) -> None:
    """`ai/TESTING.md` §13: a guard nobody has watched fail is not evidence.

    Every form the dependency could take is put through the real analyser, so narrowing it —
    dropping `sqlite3`, matching only exact module names, ignoring imports inside functions —
    fails here instead of passing silently against a tree that happens to be clean.
    """
    assert offenders(source), f"{source!r} would not have been caught"


@pytest.mark.parametrize(
    "source",
    [
        "from tracks_and_trails.core.models import Job",
        "import multiprocessing",
        # `ARC-007` forbids the settings module, not `core/` (`T-097`). Each of these is something
        # the real manager does today, and a prohibition that caught them would be deleted by
        # whoever it blocked — taking the settings gate with it.
        "from tracks_and_trails.core import logging as app_logging",
        "from tracks_and_trails.core.errors import ErrorKind",
        "from tracks_and_trails.core.job_state import JobStatus, is_terminal",
        "from tracks_and_trails.core import models",
        "import tracks_and_trails.core.models",
        # Adjacent names that merely start the same way must not be swept up.
        "from tracks_and_trails.core.settings_helpers import thing",
        "import tracks_and_trails.core.settingsish",
    ],
)
def test_a_legitimate_import_is_not_reported(source: str) -> None:
    """False positives get a check deleted by whoever they block, taking the real one with them."""
    assert not offenders(source), f"{source!r} was reported and should not be"


def test_the_modules_under_test_exist() -> None:
    """Guards against every check above passing because a path was renamed."""
    for module in MODULES:
        assert (SRC / module).is_file(), f"{module} does not exist; the checks above are vacuous"
