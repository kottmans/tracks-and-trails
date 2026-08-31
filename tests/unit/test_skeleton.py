"""Verifies T-001's own acceptance criteria: the skeleton is importable and runnable.

These are structural checks, not behavior tests. They exist so that a regression in packaging
or entry-point wiring fails here rather than at launch.
"""

import subprocess
import sys
from pathlib import Path

import tracks_and_trails


def test_package_exposes_a_version() -> None:
    assert tracks_and_trails.__version__
    assert isinstance(tracks_and_trails.__version__, str)


def test_module_entry_point_runs_and_exits_zero() -> None:
    """`python -m tracks_and_trails --version` must resolve and exit cleanly.

    Bare `python -m tracks_and_trails` opened a window and returned once `T-007` landed, so
    it can no longer stand in for "the entry point resolves". `--version` is the headless
    path: it must work with no display and without constructing a `QApplication`, which is
    what makes it usable here and in a packaging smoke test.
    """
    result = subprocess.run(
        [sys.executable, "-m", "tracks_and_trails", "--version"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout.strip() == tracks_and_trails.__version__
    assert result.stderr == "", f"unexpected stderr: {result.stderr}"


def test_entry_point_import_does_not_pull_in_qt() -> None:
    """Importing __main__ must not import Qt.

    ARC-002 requires worker processes to inherit no Qt, and ARCHITECTURE.md §3 relies on
    freeze_support() running before any Qt import. A module-level `from ... app import run`
    would quietly break both once app.py starts constructing a QApplication (T-007).

    Run in a subprocess: the pytest session itself may already have Qt loaded.
    """
    code = (
        "import sys; import tracks_and_trails.__main__; "
        "print(any(m.startswith(('PySide6', 'shiboken6')) for m in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert result.stdout.strip() == "False", "importing __main__ pulled in Qt"


def test_the_root_conftest_does_not_pull_in_qt() -> None:
    """The root `conftest.py` is imported before every suite, including the Qt-free one.

    `ai/TESTING.md` §1 makes `tests/unit/` headless and Qt-free on purpose, and that file's own
    docstring claims the property — which its pool fixture then quietly retired by importing both
    Qt-bearing pool modules for every test in the repository just to reset two module globals
    (`T289-R23`). `sys.modules` answers the same question without loading anything.

    **In a subprocess, and entering the fixture rather than only importing the file**, for the
    reason `test_entry_point_import_does_not_pull_in_qt` gives one step further: this pytest
    session already has Qt loaded through its own plugins, so nothing measured inside it could
    distinguish the fixture's imports from the session's. The fixture is driven directly as the
    generator it is.
    """
    code = (
        "import sys; sys.path.insert(0, '.'); import tests.conftest as root; "
        "loaded = lambda: any(m.startswith(('PySide6', 'shiboken6')) for m in sys.modules); "
        "assert not loaded(), 'importing tests/conftest.py pulled in Qt'; "
        "step = root._pools_are_not_shared_between_tests.__wrapped__(); "
        "next(step); "
        "assert not loaded(), 'entering the pool fixture pulled in Qt'; "
        "next(step, None); "
        "print(loaded())"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=Path(__file__).resolve().parents[2],
        check=True,
    )
    assert result.stdout.strip() == "False", f"the fixture pulled in Qt: {result.stdout}"


def test_layout_matches_architecture() -> None:
    """The four layers named in ARCHITECTURE.md §4 exist as packages."""
    pkg_root = Path(tracks_and_trails.__file__).parent
    for layer in ("core", "downloader", "persistence", "ui"):
        assert (pkg_root / layer / "__init__.py").is_file(), f"missing layer: {layer}"
