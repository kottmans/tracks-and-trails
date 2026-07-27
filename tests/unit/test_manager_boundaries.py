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
FORBIDDEN = ("tracks_and_trails.persistence", "sqlite3")


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
    ],
)
def test_the_check_above_can_actually_fail(source: str) -> None:
    """`ai/TESTING.md` §13: a guard nobody has watched fail is not evidence.

    Every form the dependency could take is put through the real analyser, so narrowing it —
    dropping `sqlite3`, matching only exact module names, ignoring imports inside functions —
    fails here instead of passing silently against a tree that happens to be clean.
    """
    assert offenders(source), f"{source!r} would not have been caught"


def test_a_legitimate_import_is_not_reported() -> None:
    """False positives get a check deleted by whoever they block, taking the real one with them."""
    assert not offenders("from tracks_and_trails.core.models import Job\nimport multiprocessing")


def test_the_modules_under_test_exist() -> None:
    """Guards against every check above passing because a path was renamed."""
    for module in MODULES:
        assert (SRC / module).is_file(), f"{module} does not exist; the checks above are vacuous"
