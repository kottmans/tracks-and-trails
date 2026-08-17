"""Where a test may create a symlink, and who has to ask first (`T-260`).

**`T-070` built the capability fixture and nothing made later tests use it.** That task found four
tests failing on an ordinary Windows desktop with a bare `OSError` naming no cause, added
`tests.capabilities.can_create_symlinks` and the `symlinks` fixture — which skips naming the
privilege — and fixed the four. Tests written afterwards did not request it, so on 2026-08-16, with
`SeCreateSymbolicLinkPrivilege` absent from `STARBASE`, **five failed with
`OSError: [WinError 1314]` while four skipped cleanly** (CI run `31966531162`).

**So the rule is about creation sites, not about tests.** The restriction this file enforces:

> **A function anywhere in the test tree that creates a symlink must request the `symlinks`
> capability.** No exceptions at module scope, none for fixtures, none for helpers, and none for
> `async def`.

That is deliberately broader than "a test body that calls `symlink_to`", which is what the first
version checked and what `T260-R1` rejected. A `conftest.py` fixture or a helper in an ordinary
module can create the link *for* an unguarded test, reaching link creation with no capability check
and raising the same bare `OSError` — while a gate that only reads synchronous `test_` functions in
`test_*.py` files reports success.

**Threading the capability through a parameter is what makes the rule propagate.** A fixture that
requests `symlinks` skips the test that uses it; a helper that takes it as an argument can only be
called from something that has it. Neither needs this gate to understand the call graph.

**Static, not a runtime `except OSError`.** Catching it at runtime would turn every future
privilege failure into a silent pass — worse than the bare error this began with, because a skip
nobody sees is indistinguishable from coverage. Reading the source fails when written, on any host,
whether or not the capability happens to be present locally. That matters: Developer Mode is now
enabled on `STARBASE`, so the original five pass there again and the gap would otherwise be
invisible.
"""

import ast
from pathlib import Path
from typing import Final

import pytest

TESTS: Final = Path(__file__).resolve().parents[1]

#: The fixture a symlink-creating function must request (`tests/capabilities.py`).
CAPABILITY: Final = "symlinks"

#: The names that create a symlink, matched however they are spelled:
#:
#: - `path.symlink_to(...)` and `os.symlink(...)` — an `ast.Attribute` call
#: - `symlink(...)` after `from os import symlink` — an `ast.Name` call (`T260-R1`)
#:
#: Matching the *name* rather than a resolved call means an unrelated method called `symlink` is
#: also flagged. **False positives are cheap here and false negatives are not**: a wrong flag costs
#: one fixture argument, a miss costs a bare `WinError 1314` on somebody's Windows machine.
SYMLINK_CALLS: Final = frozenset({"symlink_to", "symlink"})

#: `tests/capabilities.py` *is* the probe — `can_create_symlinks` creates one to find out whether it
#: can, so it cannot ask itself first.
EXEMPT: Final = frozenset({"capabilities.py"})

_Function = ast.FunctionDef | ast.AsyncFunctionDef

#: What pytest collects, from its own defaults — `pyproject.toml` overrides neither.
COLLECTED_MODULE: Final = ("test_*.py", "*_test.py")


def _is_creation(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    called = node.func
    if isinstance(called, ast.Attribute):
        return called.attr in SYMLINK_CALLS
    if isinstance(called, ast.Name):
        return called.id in SYMLINK_CALLS
    return False


def _requests(node: _Function, fixture: str) -> bool:
    arguments = node.args
    names = [a.arg for a in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)]
    return fixture in names


def _pytest_names(tree: ast.Module) -> tuple[set[str], set[str]]:
    """How this module refers to pytest: module aliases, and directly imported names.

    **Resolved from the imports rather than trusted by name** (`T260-R1`, third pass). A decorator
    spelled `fixture` proves nothing on its own — a module can define its own, or import one from
    anywhere. `@pytest.fixture` counts because `pytest` is bound to pytest *here*.
    """
    aliases: set[str] = set()
    directly: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            aliases |= {a.asname or a.name for a in node.names if a.name == "pytest"}
        elif isinstance(node, ast.ImportFrom) and node.module == "pytest":
            directly |= {a.asname or a.name for a in node.names}
    return aliases, directly


def _is_pytest_fixture(node: _Function, tree: ast.Module) -> bool:
    aliases, directly = _pytest_names(tree)
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Attribute) and target.attr == "fixture":
            root = target.value
            if isinstance(root, ast.Name) and root.id in aliases:
                return True
        elif isinstance(target, ast.Name) and target.id in directly:
            return True
    return False


def _fixture_capable_modules() -> set[str]:
    """Module stems whose fixtures reach pytest by being re-exported from a `conftest.py`.

    `tests/capabilities.py` is the live case: `tests/conftest.py` imports `symlinks` from it and
    lists it in `__all__`, so pytest resolves it even though the filename is not collectible.
    Derived rather than allowlisted, so a second such module needs no edit here.
    """
    stems = set()
    for conftest in TESTS.rglob("conftest.py"):
        for node in ast.walk(ast.parse(conftest.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                stems.add(node.module.rsplit(".", 1)[-1])
    return stems


def _resolvable(path: Path, node: _Function, tree: ast.Module) -> bool:
    """Whether **pytest** supplies this function's parameters.

    Three ways, and no others:

    - a `test_*` function in a module pytest collects — `test_*.py` or `*_test.py`;
    - a genuine `pytest.fixture` in a `conftest.py` or in a collected module;
    - a genuine `pytest.fixture` in a module a `conftest.py` re-exports from.

    A `test_`-named function in an uncollected helper module is **not** resolvable: pytest never
    sees it, so its `symlinks` parameter is whatever its caller passed (`T260-R1`, third pass).
    """
    collected = any(path.match(pattern) for pattern in COLLECTED_MODULE)
    if node.name.startswith("test_"):
        return collected
    if not _is_pytest_fixture(node, tree):
        return False
    return collected or path.name == "conftest.py" or path.stem in _fixture_capable_modules()


def _creation_sites(node: ast.AST) -> list[ast.Call]:
    return [n for n in ast.walk(node) if isinstance(n, ast.Call) and _is_creation(n)]


Site = tuple[ast.Call, list[_Function], bool]


def _scan(node: ast.AST, chain: list[_Function], import_time: bool) -> list[Site]:
    """Every creation site, its enclosing function bodies, and whether it runs at import.

    **Generic recursion over `iter_child_nodes`, not a statement-shape walker.** The previous
    version enumerated the compound statements it knew about and therefore missed the ones it did
    not — `except` handlers are `ExceptHandler`, `match` arms are `match_case`, and neither is an
    `ast.stmt`, so their bodies were never scanned (`T260-R1`, third pass). Recursing over every
    child covers the grammar rather than the parts of it somebody remembered.
    """
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        defaults = [d for d in (*node.args.defaults, *node.args.kw_defaults) if d is not None]
        found = [
            site
            for expression in (*node.decorator_list, *defaults)
            for site in _scan(expression, chain, True)
        ]
        return found + [s for stmt in node.body for s in _scan(stmt, [*chain, node], import_time)]
    if isinstance(node, ast.ClassDef):
        found = [s for d in node.decorator_list for s in _scan(d, chain, True)]
        return found + [s for stmt in node.body for s in _scan(stmt, chain, import_time)]
    here: list[Site] = []
    if isinstance(node, ast.Call) and _is_creation(node):
        here.append((node, chain, import_time))
    for child in ast.iter_child_nodes(node):
        here += _scan(child, chain, import_time)
    return here


def _sources() -> list[Path]:
    """**Every** Python file in the test tree — `conftest.py` and helpers included (`T260-R1`)."""
    return sorted(p for p in TESTS.rglob("*.py") if p.name not in EXEMPT)


def _unguarded(path: Path, source: str) -> list[str]:
    tree = ast.parse(source)
    faults = []
    for call, chain, import_time in _scan(tree, [], False):
        where = f"{path.name}:{call.lineno}"
        if import_time:
            faults.append(f"{where} creates a symlink at import time, before any fixture resolves")
        elif not chain:
            faults.append(f"{where} creates a symlink at module scope, where nothing can guard it")
        elif not any(_resolvable(path, f, tree) and _requests(f, CAPABILITY) for f in chain):
            named = " -> ".join(f.name for f in chain)
            faults.append(
                f"{where} in {named}() creates a symlink with no pytest-resolved "
                f"`{CAPABILITY}` above it"
            )
    return faults


def test_every_symlink_creation_site_asks_whether_the_machine_can() -> None:
    """The rule `T-070` could not enforce, enforced across the whole test tree.

    A creation site reached without the capability raises a bare `OSError` on any machine lacking
    the privilege — the ordinary state of a Windows desktop, not an unusual one.
    """
    faults = [
        fault for path in _sources() for fault in _unguarded(path, path.read_text(encoding="utf-8"))
    ]
    assert not faults, (
        "these create a symlink without asking whether the machine can, so they raise "
        "OSError [WinError 1314] instead of skipping:\n  " + "\n  ".join(faults) + "\n"
        f"Request the `{CAPABILITY}` fixture from tests/capabilities.py, or take it as an argument "
        "so the caller must have it."
    )


def test_this_gate_is_looking_at_something() -> None:
    """A rule that inspects nothing passes in silence, so it says how much it inspected.

    Nine creation sites existed when this was written — three in `tests/unit/test_paths.py`, six in
    `tests/integration/test_worker.py`. If that reaches zero the symlink coverage has gone, not the
    risk.
    """
    sites = sum(len(_creation_sites(ast.parse(p.read_text("utf-8")))) for p in _sources())
    assert sites >= 9, (
        f"only {sites} symlink creation sites remain; there were nine when this gate was written. "
        "If that coverage was deliberately removed, update this floor and say why."
    )
    assert len(_sources()) > 20, (
        f"the walk found only {len(_sources())} Python files under tests/, which suggests it is "
        "looking in the wrong place"
    )


# --- the detector, against every spelling T260-R1 named -----------------------------------------

#: Spellings that must be flagged, each with the filename it would really live in — because
#: resolvability depends on whether pytest collects that file at all.
_TEST_FILE: Final = Path("test_probe.py")
_HELPER_FILE: Final = Path("helpers.py")
_CONFTEST: Final = Path("conftest.py")

_UNGUARDED: Final = {
    "sync-test-attribute": (
        _TEST_FILE,
        "def test_x(tmp_path):\n    (tmp_path / 'l').symlink_to(tmp_path)\n",
    ),
    "os-attribute": (
        _TEST_FILE,
        "import os\ndef test_x(tmp_path):\n    os.symlink(tmp_path, tmp_path / 'l')\n",
    ),
    "direct-import": (
        _TEST_FILE,
        "from os import symlink\ndef test_x(tmp_path):\n    symlink(tmp_path, tmp_path / 'l')\n",
    ),
    "async-test": (
        _TEST_FILE,
        "async def test_x(tmp_path):\n    (tmp_path / 'l').symlink_to(tmp_path)\n",
    ),
    "conftest-fixture": (
        _CONFTEST,
        "import pytest\n@pytest.fixture\ndef planted(tmp_path):\n"
        "    (tmp_path / 'l').symlink_to(tmp_path)\n    return tmp_path\n",
    ),
    "helper-function": (
        _TEST_FILE,
        "def plant_a_symlink(tmp_path):\n    (tmp_path / 'l').symlink_to(tmp_path)\n",
    ),
    "module-scope": (_TEST_FILE, "from pathlib import Path\nPath('l').symlink_to(Path('.'))\n"),
    "nested-helper": (
        _TEST_FILE,
        "def test_x(tmp_path):\n    def inner():\n        (tmp_path / 'l').symlink_to(tmp_path)\n"
        "    inner()\n",
    ),
    # T260-R1's surviving case, verbatim: the helper takes a parameter *named* `symlinks`, and an
    # unguarded test calls it with None. pytest never resolved anything.
    "helper-named-parameter": (
        _TEST_FILE,
        "def plant(path, symlinks):\n    path.symlink_to(path)\n\n"
        "def test_x(tmp_path):\n    plant(tmp_path, None)\n",
    ),
    "helper-defaulted-parameter": (
        _TEST_FILE,
        "def plant(path, symlinks=None):\n    path.symlink_to(path)\n\n"
        "def test_x(tmp_path):\n    plant(tmp_path)\n",
    ),
    # Decorators and defaults run at import, before any fixture resolves.
    "decorator-expression": (
        _TEST_FILE,
        "import pytest\nfrom pathlib import Path\n"
        "@pytest.mark.parametrize('x', [Path('l').symlink_to(Path('.'))])\n"
        "def test_x(x, symlinks):\n    pass\n",
    ),
    "parameter-default": (
        _TEST_FILE,
        "from pathlib import Path\n"
        "def test_x(symlinks, planted=Path('l').symlink_to(Path('.'))):\n    pass\n",
    ),
    # `T260-R1`, third pass: pytest never collects an uncollected module, so its `test_`-named
    # function's parameters are whatever its caller passed.
    "test-named-function-in-a-helper-module": (
        _HELPER_FILE,
        "def test_x(tmp_path, symlinks):\n    (tmp_path / 'l').symlink_to(tmp_path)\n",
    ),
    # A decorator merely *named* `fixture` is not pytest's.
    "home-grown-fixture-decorator": (
        _CONFTEST,
        "def fixture(fn):\n    return fn\n\n@fixture\ndef planted(tmp_path, symlinks):\n"
        "    (tmp_path / 'l').symlink_to(tmp_path)\n",
    ),
    # Grammar the previous statement-shape walker never descended into.
    "inside-an-except-handler": (
        _TEST_FILE,
        "def test_x(tmp_path):\n    try:\n        pass\n    except ValueError:\n"
        "        (tmp_path / 'l').symlink_to(tmp_path)\n",
    ),
    "inside-a-match-case": (
        _TEST_FILE,
        "def test_x(tmp_path, kind):\n    match kind:\n        case 'link':\n"
        "            (tmp_path / 'l').symlink_to(tmp_path)\n",
    ),
    "inside-a-with-in-an-else": (
        _TEST_FILE,
        "import contextlib\ndef test_x(tmp_path):\n    if False:\n        pass\n    else:\n"
        "        with contextlib.suppress(OSError):\n"
        "            (tmp_path / 'l').symlink_to(tmp_path)\n",
    ),
}

_GUARDED: Final = {
    "sync-test": (
        _TEST_FILE,
        "def test_x(tmp_path, symlinks):\n    (tmp_path / 'l').symlink_to(tmp_path)\n",
    ),
    "async-test": (
        _TEST_FILE,
        "async def test_x(tmp_path, symlinks):\n    (tmp_path / 'l').symlink_to(tmp_path)\n",
    ),
    "fixture-requesting-it": (
        _CONFTEST,
        "import pytest\n@pytest.fixture\ndef planted(tmp_path, symlinks):\n"
        "    (tmp_path / 'l').symlink_to(tmp_path)\n    return tmp_path\n",
    ),
    "fixture-imported-directly": (
        _CONFTEST,
        "from pytest import fixture\n@fixture\ndef planted(tmp_path, symlinks):\n"
        "    (tmp_path / 'l').symlink_to(tmp_path)\n",
    ),
    "fixture-with-arguments": (
        _CONFTEST,
        "import pytest\n@pytest.fixture(scope='function')\ndef planted(tmp_path, symlinks):\n"
        "    (tmp_path / 'l').symlink_to(tmp_path)\n",
    ),
    "keyword-only": (
        _TEST_FILE,
        "def test_x(tmp_path, *, symlinks):\n    (tmp_path / 'l').symlink_to(tmp_path)\n",
    ),
    "closure-inside-a-guarded-test": (
        _TEST_FILE,
        "def test_x(tmp_path, symlinks):\n    def plant():\n"
        "        (tmp_path / 'l').symlink_to(tmp_path)\n    plant()\n",
    ),
    "guarded-inside-an-except-handler": (
        _TEST_FILE,
        "def test_x(tmp_path, symlinks):\n    try:\n        pass\n    except ValueError:\n"
        "        (tmp_path / 'l').symlink_to(tmp_path)\n",
    ),
}


@pytest.mark.parametrize("spelling", sorted(_UNGUARDED), ids=sorted(_UNGUARDED))
def test_the_detector_catches_every_unguarded_spelling(spelling: str) -> None:
    """The mutations, run rather than described.

    **`T260-R1` found four of these undiscovered by the first version**: a `conftest.py` fixture, a
    helper in an ordinary module, `async def`, and `from os import symlink`. Each is a real route to
    the bare `WinError 1314` the task exists to remove, so each is a case here.
    """
    path, source = _UNGUARDED[spelling]
    assert _unguarded(path, source), (
        f"the detector does not see {spelling}, so the gate would pass while this spelling ships"
    )


@pytest.mark.parametrize("spelling", sorted(_GUARDED), ids=sorted(_GUARDED))
def test_the_detector_accepts_a_guarded_site(spelling: str) -> None:
    """The other direction, so the gate cannot pass by calling everything unguarded."""
    path, source = _GUARDED[spelling]
    assert not _unguarded(path, source)
