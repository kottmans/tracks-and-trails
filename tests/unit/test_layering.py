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
from typing import Final

import pytest

#: Located from this file's own path rather than by importing the package. Importing
#: `tracks_and_trails` to read `__file__` would execute its `__init__`, contradicting this
#: module's whole premise, and would analyze whichever copy happens to be installed rather
#: than the source tree in this checkout (`T005-R2`).
SRC = Path(__file__).resolve().parents[2] / "src" / "tracks_and_trails"

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


# ---------------------------------------------------------------------------
# An independent restatement of the architecture.
#
# Everything above describes how the rules are *implemented*. Everything below describes what
# the rules must *achieve*, derived from ARCHITECTURE.md straight from a file path and sharing
# no constant or predicate with RULES. That separation is the point (`T005-R1`): the original
# self-tests asserted the analyzer's behavior at a handful of hardcoded paths, so narrowing a
# rule to exactly those paths — or adding a third yt-dlp owner — left every test green. Two
# statements that must agree cannot be routed around by editing one of them.
# ---------------------------------------------------------------------------

#: ARCHITECTURE.md §6 and NFR-008, written out literally. If `YTDLP_OWNERS` above gains an
#: entry, this does not move with it and the disagreement fails the suite.
ARCH_YTDLP_OWNERS = frozenset({"downloader/worker.py", "downloader/ytdlp_adapter.py"})

#: ARCHITECTURE.md §4, written out literally, for the same reason.
ARCH_QT_PACKAGES = frozenset({"PySide6", "shiboken6"})
ARCH_YTDLP_PACKAGES = frozenset({"yt_dlp"})


def architecture_forbids(rel_path: str) -> frozenset[str]:
    """What `ARCHITECTURE.md` says this file may not import, read straight from its path."""
    forbidden: set[str] = set()
    # §4: core/ is pure Python, no Qt. §4 bullets + ARC-002: the worker inherits no Qt.
    if rel_path.startswith("core/") or rel_path == "downloader/worker.py":
        forbidden |= ARCH_QT_PACKAGES
    # §6 + NFR-008: exactly two modules may import yt-dlp; ui/ is covered by this too.
    if rel_path not in ARCH_YTDLP_OWNERS:
        forbidden |= ARCH_YTDLP_PACKAGES
    return frozenset(forbidden)


def test_the_owner_allowlist_matches_the_architecture() -> None:
    """`YTDLP_OWNERS` may not quietly grow a third entry (`T005-R1`)."""
    assert frozenset(YTDLP_OWNERS) == ARCH_YTDLP_OWNERS, (
        "YTDLP_OWNERS disagrees with ARCHITECTURE.md §6. Widening the allowlist is an "
        "architecture change and needs a Planner decision, not a test edit."
    )


def effective_forbidden(rel_path: str) -> frozenset[str]:
    """Everything `RULES` will actually reject for `rel_path` — the analyzer's real behavior."""
    return frozenset().union(*(r.forbidden for r in RULES if r.applies_to(rel_path)), frozenset())


@pytest.mark.parametrize("path", source_files(), ids=rel)
def test_every_module_is_actually_guarded(path: Path) -> None:
    """For every real module, the analyzer must catch every import the architecture forbids.

    The behavioral half of `T005-R1`: it exercises `check()` end to end over the real tree
    rather than a fixture list, so narrowing any rule's `applies_to` leaves some module
    unguarded and fails here, as does dropping a package from `QT` or `YTDLP`.
    """
    rel_path = rel(path)
    for package in sorted(architecture_forbids(rel_path)):
        violations = check(rel_path, f"import {package}")
        assert violations, (
            f"{rel_path} may not import {package} per ARCHITECTURE.md §4/§6, but no rule in "
            f"RULES would catch it. The enforcement has a hole at this path."
        )


@pytest.mark.parametrize("path", source_files(), ids=rel)
def test_every_module_is_guarded_no_more_than_the_architecture_requires(path: Path) -> None:
    """The two statements of the architecture must agree **exactly**, in both directions.

    `test_every_module_is_actually_guarded` proves no required prohibition is missing. This
    proves no *surplus* prohibition has been added — the one-way gap the first fix left open.
    Adding an architecture-allowed package such as `typing` to `QT`, or widening a rule onto a
    layer where its package is permitted, changes what the analyzer rejects without changing
    what `ARCHITECTURE.md` forbids, and that disagreement fails here.

    Surplus prohibitions matter as much as missing ones: a rule that rejects legitimate code
    gets loosened or deleted by whoever it blocks, taking the real protection with it.
    """
    rel_path = rel(path)
    assert effective_forbidden(rel_path) == architecture_forbids(rel_path), (
        f"RULES and ARCHITECTURE.md disagree about {rel_path}.\n"
        f"  RULES reject:        {sorted(effective_forbidden(rel_path))}\n"
        f"  ARCHITECTURE forbids: {sorted(architecture_forbids(rel_path))}\n"
        "Changing what a layer may import is an architecture decision, not a test edit."
    )


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


# ---------------------------------------------------------------------------
# T-214: the two gaps the four rules above never covered.
#
# Everything before this point enforces *external* dependencies — Qt and yt-dlp. Nothing in it
# fails if `core/` imports `ui/`, and nothing in it holds a module to a Qt-freedom its own
# docstring promises. Both gaps were real rather than theoretical: `core/logging.py`,
# `core/paths.py` and `persistence/db.py` all imported upward from `downloader/` for one string
# constant, and the audit that filed this task recorded the tree as clean in every internal
# direction. It was not. That is what an unenforced rule looks like from the outside.
# ---------------------------------------------------------------------------

#: `ARCHITECTURE.md` §4's diagram, transcribed: which subpackage may import which.
#:
#: *"Dependencies point downward only"*, over the four layers the diagram draws — `ui/` on top,
#: `downloader/` and `persistence/` beside each other, `core/` at the bottom. A layer may import
#: anything below it and nothing at its own level or above.
#:
#: **`downloader/` and `persistence/` are siblings, so neither may import the other.** The diagram
#: puts them on one line; `persistence/db.py` crossed that line for `APP_SLUG` until `T-214` moved
#: the constant down to where every layer can reach it.
MAY_IMPORT: Final = {
    "core": frozenset(),
    "persistence": frozenset({"core"}),
    "downloader": frozenset({"core"}),
    "ui": frozenset({"core", "downloader", "persistence"}),
}

#: §4's diagram again, transcribed a **second** time and differently — as each layer's height on
#: it, rather than as a map of who may import whom.
#:
#: **The two statements share no constant, and that is the whole point** (`T005-R1`, applied here
#: for the reason it was applied above). `test_each_forbidden_direction_is_actually_caught` derives
#: its cases from `MAY_IMPORT`, so widening `MAY_IMPORT` does not fail it — it just deletes a case.
#: Both of the obvious wrong edits (*let `core/` see `downloader/`*, *let the two siblings see each
#: other*) were tried against an earlier version of this file and passed, which is why this exists.
#:
#: `downloader/` and `persistence/` share a height because the diagram draws them on one line.
ARCH_LAYER_HEIGHT: Final = {"core": 0, "persistence": 1, "downloader": 1, "ui": 2}


def architecture_allows(layer: str) -> frozenset[str]:
    """What §4's *"downward only"* permits `layer` to import, from the diagram's heights alone."""
    return frozenset(
        other for other, height in ARCH_LAYER_HEIGHT.items() if height < ARCH_LAYER_HEIGHT[layer]
    )


@pytest.mark.parametrize("layer", sorted(MAY_IMPORT))
def test_the_direction_map_matches_the_architecture(layer: str) -> None:
    """`MAY_IMPORT` may not quietly widen, in either direction.

    Exactly the guarantee `test_the_owner_allowlist_matches_the_architecture` gives `YTDLP_OWNERS`.
    Loosening a layer is an architecture change and needs a Planner decision, not a test edit —
    and tightening one silently is how a rule starts rejecting legitimate code and gets deleted by
    whoever it blocks.
    """
    assert MAY_IMPORT[layer] == architecture_allows(layer), (
        f"MAY_IMPORT and ARCHITECTURE.md §4 disagree about what {layer}/ may import: the map says "
        f"{sorted(MAY_IMPORT[layer])}, the diagram's heights say "
        f"{sorted(architecture_allows(layer))}."
    )


#: Modules at the package root — `app.py`, `__main__.py`, `_freeze_probe.py`. `ARCHITECTURE.md` §4
#: calls these wiring rather than a layer, and wiring is allowed to see everything it wires.
ROOT = "(root)"


def layer_of(rel_path: str) -> str:
    """Which layer a file belongs to, from its path alone."""
    head = rel_path.split("/")[0]
    return head if head in MAY_IMPORT else ROOT


PACKAGE: Final = "tracks_and_trails"


def module_name_of(rel_path: str) -> str:
    """The dotted module name of a file, so an import can be resolved back to it."""
    parts = rel_path.removesuffix(".py").split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join([PACKAGE, *parts])


def containing_package_of(rel_path: str) -> list[str]:
    """The package a relative import in `rel_path` counts levels *from*."""
    parts = rel_path.removesuffix(".py").split("/")
    if parts[-1] != "__init__":
        parts = parts[:-1]
    return [PACKAGE, *parts]


def internal_imports(source: str, rel_path: str) -> set[str]:
    """Every module **inside this package** that `rel_path` imports, as dotted names.

    **Relative imports are resolved rather than skipped, and that was `T214-R1`.** The first
    version tested `node.level == 0` and returned early otherwise — reasoning, in a comment it
    inherited from `imported_roots`, that *"relative imports are intra-package by definition and
    cannot name a third-party root"*. True for the Qt and yt-dlp rules; the exact opposite of what
    the internal-direction rule needs, since intra-package is precisely what it governs.
    `from ..ui import theme` inside `core/` therefore passed, and every synthetic mutation case
    used absolute imports, so nothing noticed.

    `from X import y` contributes **both** `X` and `X.y`, because `from tracks_and_trails.ui import
    theme` names a module in its second half, not an attribute.
    """
    found: set[str] = set()
    for node in ast.walk(ast.parse(source, filename=rel_path)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == PACKAGE or alias.name.startswith(f"{PACKAGE}."):
                    found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = containing_package_of(rel_path)
                # level 1 is the containing package, each further level one above it.
                trimmed = base[: len(base) - (node.level - 1)] if node.level > 1 else base
                if not trimmed:
                    continue
                prefix = ".".join(trimmed)
                module = f"{prefix}.{node.module}" if node.module else prefix
            elif node.module and (node.module == PACKAGE or node.module.startswith(f"{PACKAGE}.")):
                module = node.module
            else:
                continue
            found.add(module)
            found.update(f"{module}.{alias.name}" for alias in node.names)
    # **Only the names that are really modules.** `from tracks_and_trails import __version__`
    # contributes `tracks_and_trails.__version__`, which is a constant in the package's `__init__`
    # rather than a file — and counting it made `ui/main_window.py` look like it imported from the
    # package root. Resolving against the tree is the filter, and it is the same resolution the
    # Qt-freedom walk needs, so there is one of it.
    return {module for module in found if file_for_module(module) is not None}


def file_for_module(dotted: str) -> Path | None:
    """The file a dotted module name names, or `None` if it names something that is not a module."""
    if dotted != PACKAGE and not dotted.startswith(f"{PACKAGE}."):
        return None
    parts = dotted.split(".")[1:]
    for candidate in (SRC.joinpath(*parts).with_suffix(".py"), SRC.joinpath(*parts, "__init__.py")):
        if candidate.is_file():
            return candidate
    return None


def internal_targets(source: str, filename: str) -> set[str]:
    """The layers `filename` imports from, by name.

    `imported_roots` cannot answer this: every intra-project import has the same top-level root,
    `tracks_and_trails`, so the four rules above see `from tracks_and_trails.ui import theme` and
    `from tracks_and_trails.core import models` as the same import.
    """
    targets: set[str] = set()
    for module in internal_imports(source, filename):
        parts = module.split(".")
        if len(parts) > 1:
            targets.add(parts[1] if parts[1] in MAY_IMPORT else ROOT)
    return targets


def upward_imports(rel_path: str, source: str) -> list[str]:
    """Every import this file makes that `ARCHITECTURE.md` §4 does not allow from its layer."""
    layer = layer_of(rel_path)
    if layer == ROOT:
        return []
    allowed = MAY_IMPORT[layer]
    return sorted(
        f"{rel_path} imports {target}/ — {layer}/ may import "
        f"{sorted(allowed) or 'nothing inside the package'} "
        "(ARCHITECTURE.md §4: dependencies point downward only)"
        for target in internal_targets(source, rel_path)
        if target != layer and target not in allowed
    )


@pytest.mark.parametrize("path", source_files(), ids=rel)
def test_no_module_imports_upward_or_sideways(path: Path) -> None:
    """`ARCHITECTURE.md` §4's *"dependencies point downward only"*, enforced rather than stated.

    This is the rule the file's own header called *"the project's central architectural bet"* and
    then did not check. Three modules were breaking it when this test was written.
    """
    violations = upward_imports(rel(path), path.read_text(encoding="utf-8"))
    assert not violations, "\n".join(violations)


#: The ways Python spells an import, so the guard is proved against the **grammar** and not only
#: against the spelling I happened to use (`T214-R1`).
#:
#: Every synthetic case in the first version was absolute, and `internal_targets` tested
#: `node.level == 0` — so relative imports bypassed the whole rule and no mutation could see it.
#: A guard proved against one grammar is a guard against one grammar.
#: One real module per layer, because the guard resolves imports against the tree. A synthetic
#: `tracks_and_trails.ui.something` names no file and is correctly ignored, so the probes have to
#: name modules that exist — `test_the_probe_modules_exist` keeps that honest if one is renamed.
A_MODULE_IN: Final = {
    "core": "models",
    "persistence": "db",
    "downloader": "manager",
    "ui": "theme",
}

IMPORT_GRAMMARS: Final = {
    "absolute-from-package": lambda target: f"from {PACKAGE}.{target} import {A_MODULE_IN[target]}",
    "absolute-from-module": lambda target: (
        f"from {PACKAGE}.{target}.{A_MODULE_IN[target]} import something"
    ),
    "absolute-import": lambda target: f"import {PACKAGE}.{target}.{A_MODULE_IN[target]}",
    "relative-from-package": lambda target: f"from ..{target} import {A_MODULE_IN[target]}",
    "relative-from-module": lambda target: (
        f"from ..{target}.{A_MODULE_IN[target]} import something"
    ),
}


def test_the_probe_modules_exist() -> None:
    """A probe naming a module that was renamed away proves nothing, silently.

    Every case below asserts that a forbidden import *is caught*. Resolution against the tree is
    what makes the guard ignore names that are not modules — so a stale name here would turn every
    one of those cases into an assertion about nothing.
    """
    missing = sorted(
        f"{layer}/{name}.py"
        for layer, name in A_MODULE_IN.items()
        if not (SRC / layer / f"{name}.py").is_file()
    )
    assert not missing, f"the direction probes name modules that no longer exist: {missing}"


@pytest.mark.parametrize("grammar", sorted(IMPORT_GRAMMARS))
@pytest.mark.parametrize(
    ("importer", "target"),
    [
        (importer, target)
        for importer in MAY_IMPORT
        for target in MAY_IMPORT
        if target != importer and target not in MAY_IMPORT[importer]
    ],
    ids=lambda value: value,
)
def test_each_forbidden_direction_is_actually_caught(
    importer: str, target: str, grammar: str
) -> None:
    """**The rule is mutation-checked, not only the tree** — this task's first criterion.

    A tree that happens to be clean says nothing about whether the guard works; the guard passing
    on a synthetic violation of *every* forbidden direction does. Seven directions are forbidden
    by `MAY_IMPORT`, and each gets its own case, so narrowing the rule to catch six of them fails
    here rather than silently reducing what is defended.
    """
    source = IMPORT_GRAMMARS[grammar](target)
    assert upward_imports(f"{importer}/probe.py", source), (
        f"{importer}/ importing {target}/ is forbidden by ARCHITECTURE.md §4, and the guard does "
        f"not catch it written as {grammar}: {source!r}"
    )


def test_a_downward_import_is_not_caught() -> None:
    """The other direction, so the guard cannot pass by rejecting everything.

    A rule that flagged every internal import would satisfy every case above and would be deleted
    within a week by whoever it blocked — which is the failure mode
    `test_every_module_is_guarded_no_more_than_the_architecture_requires` exists to prevent for the
    external rules.
    """
    assert not upward_imports("ui/probe.py", "from tracks_and_trails.core import models")
    assert not upward_imports("downloader/probe.py", "from tracks_and_trails.core import models")
    assert not upward_imports("persistence/probe.py", "from tracks_and_trails.core import models")
    assert not upward_imports("app.py", "from tracks_and_trails.ui import main_window")


#: The `ui/` modules that are **deliberately Qt-free**, each one's docstring says so, and until
#: `T-214` nothing held them to it (`ARCHITECTURE.md` §4).
#:
#: Roughly 1,700 lines between them. `ui/staging.py` is the type the add dialog's whole commit path
#: is built on and `ui/reveal.py` launches OS processes with no Qt at all — either could grow a
#: `PySide6` import tomorrow, and every existing test would still pass.
#:
#: **The list is here rather than in a docstring somewhere** because this is where its next author
#: meets it: adding a module to `ui/` and finding this list is how the intent survives the person
#: who had it. Removing a name from this list is a decision about the module, not a test edit —
#: `test_the_qt_free_list_names_only_modules_that_exist` makes deleting one on the way past fail.
QT_FREE_UI: Final = frozenset(
    {
        "ui/staging.py",
        "ui/reveal.py",
        "ui/format_selection.py",
        "ui/format_text.py",
        "ui/row_verbs.py",
        "ui/playlist_selection.py",
        "ui/grouping.py",
        # `T-201`: a table of sentences, and its own docstring says so. Held here for the same
        # reason as `format_text.py` beside it — the words a user reads should be assertable
        # without a display.
        "ui/error_text.py",
    }
)


def qt_reached_from(rel_path: str) -> list[str]:
    """Every module reachable from `rel_path` by internal imports that pulls Qt in.

    **Direct roots are not the property these modules promise, and that was `T214-R2`.** The
    first version asked only whether `PySide6` appeared in the file itself — so a listed module
    could `from tracks_and_trails.ui import theme`, become Qt-dependent the moment it is imported,
    and still pass, because its one direct root was `tracks_and_trails`. What the list claims is
    that these modules stay importable headless; that is a statement about everything the import
    *reaches*, not about which spellings appear in one file.

    Returns the chain, so a failure names the route rather than only the destination.
    """
    start = SRC / rel_path
    seen = {rel_path}
    # Each entry is the path and how it was reached, so the message can show the whole route.
    queue: list[tuple[Path, list[str]]] = [(start, [rel_path])]
    reached: list[str] = []
    while queue:
        path, route = queue.pop()
        source = path.read_text(encoding="utf-8")
        here = rel(path)
        if imported_roots(source, here) & QT:
            reached.append(" -> ".join(route))
            continue
        for module in sorted(internal_imports(source, here)):
            target = file_for_module(module)
            if target is None:
                continue
            target_rel = rel(target)
            if target_rel in seen:
                continue
            seen.add(target_rel)
            queue.append((target, [*route, target_rel]))
    return reached


@pytest.mark.parametrize("rel_path", sorted(QT_FREE_UI))
def test_the_deliberately_qt_free_ui_modules_stay_qt_free(rel_path: str) -> None:
    """Eight modules promise this in their own docstrings; now something checks.

    They are not merely Qt-free by accident — being Qt-free is what makes them unit-testable
    headless and what would make moving them into `core/` a straightforward change if the Planner
    ever rules on it (this task's out-of-scope note). A `PySide6` import in any of them takes that
    away silently.
    """
    routes = qt_reached_from(rel_path)
    assert not routes, (
        f"{rel_path} reaches Qt:\n  " + "\n  ".join(routes) + "\nIts docstring says it is "
        "Qt-free, and being Qt-free is what makes it importable and unit-testable headless — a "
        "property an indirect import destroys just as completely as a direct one. If the import "
        "is genuinely needed, remove the module from QT_FREE_UI and say why; do not weaken this."
    )


def test_the_qt_free_list_names_only_modules_that_exist() -> None:
    """A stale name is a rule that silently stops covering anything (`T005-R1`'s shape).

    If `ui/grouping.py` is renamed and this list is not, the parametrised test above would fail on
    a missing file — but if someone *deletes* a name to make a failure go away, nothing would
    notice. This does.
    """
    missing = sorted(name for name in QT_FREE_UI if not (SRC / name).exists())
    assert not missing, f"QT_FREE_UI names modules that no longer exist: {missing}"

    # Empty `__init__.py` files import nothing at all, which is not the same claim: they are
    # Qt-free because there is nothing in them, not because someone decided to keep logic out of
    # Qt's reach. Holding them to this would make the list mean two different things.
    actually_free = {
        rel(path)
        for path in source_files()
        if rel(path).startswith("ui/")
        and path.name != "__init__.py"
        and not qt_reached_from(rel(path))
    }
    dropped = actually_free - QT_FREE_UI
    assert not dropped, (
        f"these ui/ modules import no Qt but are not held to it: {sorted(dropped)}. Either add "
        "them to QT_FREE_UI, or — if being Qt-free is incidental rather than intended — say so in "
        "the module's own docstring and add it to the exceptions here."
    )


def test_the_qt_walk_follows_more_than_one_hop() -> None:
    """**`T214-R2`.** Qt-freedom is about what an import *reaches*, not what a file spells.

    A listed module could `from tracks_and_trails.ui import theme`, become Qt-dependent the instant
    it is imported, and pass a direct-roots check — its only direct root being `tracks_and_trails`.

    Proved on a real chain rather than a synthetic one: `__main__.py` names no Qt itself and
    reaches it through `app.py`. If the walk ever stops following internal imports, this route
    collapses to nothing and this fails.
    """
    routes = qt_reached_from("__main__.py")

    assert routes, "__main__.py reaches Qt through app.py, and the walk did not find it"
    assert any("->" in route for route in routes), (
        f"every route found is a single file, so the walk is not following imports: {routes}"
    )
