"""Enforces the layer boundaries in `ARCHITECTURE.md` §4 and §6 (`T-005`).

These rules are the project's central architectural bet. `core/` and `downloader/worker.py`
run in headless child processes and must stay importable without a display (`ARC-002`), and
yt-dlp churn is confined to two modules so an upstream change is absorbable by editing two
files (`NFR-008`). Both erode silently: nothing fails at runtime the day someone adds
`from PySide6.QtCore import QObject` to `core/models.py`, and by the time it does the
dependency is load-bearing.

The analysis is **static**. Importing each module to inspect its `sys.modules` would defeat
the purpose — it would execute module-level code, and a module that imports Qt lazily inside
a function would pass while still breaking the frozen worker.

Known limits, stated rather than implied: this reads `import` statements only. A dynamic
`importlib.import_module("PySide6")` or an `__import__` call is not detected. That is an
accepted trade-off, not an oversight — those are conspicuous in review in a way a plain import
is not. `test_the_analyzer_detects_synthetic_violations` guards the analyzer itself, because a
layering test that has been quietly weakened looks exactly like one that passes.
"""

import ast
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

import tracks_and_trails

SRC = Path(tracks_and_trails.__file__).parent

QT = frozenset({"PySide6", "shiboken6"})
YTDLP = frozenset({"yt_dlp"})

#: The only two modules permitted to import yt-dlp (`ARCHITECTURE.md` §6, `NFR-008`).
YTDLP_OWNERS = ("downloader/worker.py", "downloader/ytdlp_adapter.py")


@dataclass(frozen=True)
class Rule:
    """One layer boundary: the files it governs and the top-level packages they may not import."""

    name: str
    forbidden: frozenset[str]
    applies_to: Callable[[str], bool]
    why: str


RULES = (
    Rule(
        name="core/ must not import Qt",
        forbidden=QT,
        applies_to=lambda rel: rel.startswith("core/"),
        why="core/ is pure domain logic and must stay importable headless (ARCHITECTURE.md §4)",
    ),
    Rule(
        name="downloader/worker.py must not import Qt",
        forbidden=QT,
        applies_to=lambda rel: rel == "downloader/worker.py",
        why="the worker is a spawned child process and must inherit no Qt (ARC-002)",
    ),
    Rule(
        name="ui/ must not import yt-dlp",
        forbidden=YTDLP,
        applies_to=lambda rel: rel.startswith("ui/"),
        why="all yt-dlp access goes through the download manager (ARC-002)",
    ),
    Rule(
        name="only worker.py and ytdlp_adapter.py may import yt-dlp",
        forbidden=YTDLP,
        applies_to=lambda rel: rel not in YTDLP_OWNERS,
        why="yt-dlp churn is confined to two modules so upstream changes stay absorbable (NFR-008)",
    ),
)


def imported_roots(source: str, filename: str) -> set[str]:
    """Return the top-level package names imported by `source`.

    Covers imports anywhere in the file, including inside functions and `TYPE_CHECKING`
    blocks — a lazy import is still an import for our purposes. Relative imports are
    intra-package by definition and cannot name a third-party root, so they are skipped.
    """
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source, filename=filename)):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def check(rel_path: str, source: str) -> list[str]:
    """Return a violation message for every rule `rel_path` breaks."""
    roots = imported_roots(source, rel_path)
    return [
        f"{rel_path} imports {sorted(roots & rule.forbidden)} — violates: {rule.name}. {rule.why}"
        for rule in RULES
        if rule.applies_to(rel_path) and roots & rule.forbidden
    ]


def source_files() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def rel(path: Path) -> str:
    return path.relative_to(SRC).as_posix()


def test_source_tree_is_not_empty() -> None:
    """Guards against the suite passing because the glob silently matched nothing."""
    assert len(source_files()) >= 20, (
        "the package tree looks wrong; every other check in this file is vacuous"
    )


@pytest.mark.parametrize("path", source_files(), ids=rel)
def test_module_respects_the_layer_rules(path: Path) -> None:
    violations = check(rel(path), path.read_text(encoding="utf-8"))
    assert not violations, "\n".join(violations)


def test_the_yt_dlp_owners_exist() -> None:
    """The two-module allowlist must name real files, or the rule silently permits nothing."""
    for owner in YTDLP_OWNERS:
        assert (SRC / owner).is_file(), f"{owner} is named in YTDLP_OWNERS but does not exist"


@pytest.mark.parametrize(
    ("rel_path", "source", "expected_rule"),
    [
        ("core/models.py", "import PySide6", "core/ must not import Qt"),
        ("core/models.py", "from PySide6.QtCore import QObject", "core/ must not import Qt"),
        ("core/models.py", "import shiboken6", "core/ must not import Qt"),
        (
            "core/paths.py",
            "def f():\n    import PySide6.QtWidgets\n",
            "core/ must not import Qt",
        ),
        (
            "downloader/worker.py",
            "from PySide6 import QtCore",
            "downloader/worker.py must not import Qt",
        ),
        ("ui/main_window.py", "import yt_dlp", "ui/ must not import yt-dlp"),
        (
            "persistence/db.py",
            "import yt_dlp",
            "only worker.py and ytdlp_adapter.py may import yt-dlp",
        ),
    ],
)
def test_the_analyzer_detects_synthetic_violations(
    rel_path: str, source: str, expected_rule: str
) -> None:
    """The guard must itself be guarded.

    `ai/REVIEWS.md` names layering as an area where "the enforcement test can be weakened as
    easily as bypassed". If someone narrows a rule's `applies_to` or drops a package from
    `forbidden`, the tree still passes and nothing else notices. These synthetic cases fail
    the moment the analyzer stops catching what it is supposed to catch.
    """
    violations = check(rel_path, source)
    assert violations, f"{rel_path} breaking {expected_rule!r} was not detected"
    assert any(expected_rule in v for v in violations), violations
    assert any(rel_path in v for v in violations), "the message must name the offending file"


@pytest.mark.parametrize(
    ("rel_path", "source"),
    [
        ("downloader/worker.py", "import yt_dlp"),
        ("downloader/ytdlp_adapter.py", "from yt_dlp import YoutubeDL"),
        ("downloader/manager.py", "from PySide6.QtCore import QObject"),
        ("ui/main_window.py", "from PySide6.QtWidgets import QMainWindow"),
        ("core/models.py", "from dataclasses import dataclass"),
        ("core/models.py", "from . import job_state"),
    ],
)
def test_the_analyzer_permits_what_the_architecture_allows(rel_path: str, source: str) -> None:
    """False positives damage as much as false negatives: a rule nobody can satisfy gets deleted."""
    assert not check(rel_path, source)
