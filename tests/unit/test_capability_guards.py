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


def _pytest_managed(node: _Function) -> bool:
    """Whether pytest resolves this function's parameters as fixtures.

    **This is the distinction `T260-R1` turned on.** A parameter named `symlinks` only means the
    capability was checked if *pytest* supplied it — which happens for a collected test and for a
    declared fixture, and for nothing else. An ordinary helper's caller can pass anything, and
    `symlinks` is a `None`-returning fixture, so `plant(tmp_path, None)` is indistinguishable from
    the real thing. Taking the parameter proved nothing.
    """
    if node.name.startswith("test_"):
        return True
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Attribute) and target.attr == "fixture":
            return True
        if isinstance(target, ast.Name) and target.id == "fixture":
            return True
    return False


def _creation_sites(tree: ast.AST) -> list[ast.Call]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call) and _is_creation(n)]


def _at_import_time(node: _Function) -> list[ast.Call]:
    """Creation calls in a function's decorators or parameter defaults.

    These run when the module is imported — **before any fixture resolves** — so the enclosing
    function's own guard cannot cover them, however it is declared (`T260-R1`).
    """
    defaults = [d for d in (*node.args.defaults, *node.args.kw_defaults) if d is not None]
    return [
        call
        for expression in (*node.decorator_list, *defaults)
        for call in _creation_sites(expression)
    ]


def _walk(
    statements: list[ast.stmt], chain: list[_Function]
) -> list[tuple[ast.Call, list[_Function], bool]]:
    """Every creation site with the function bodies enclosing it, and whether it runs at import.

    Bodies only: a function's decorators and defaults are collected separately, because they execute
    at a different time from its body and a guard on the body does not reach them.
    """
    found: list[tuple[ast.Call, list[_Function], bool]] = []
    for statement in statements:
        if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
            found += [(call, chain, True) for call in _at_import_time(statement)]
            found += _walk(statement.body, [*chain, statement])
        elif isinstance(statement, ast.ClassDef):
            found += [
                (call, chain, True)
                for decorator in statement.decorator_list
                for call in _creation_sites(decorator)
            ]
            found += _walk(statement.body, chain)
        else:
            nested = [
                n
                for n in ast.walk(statement)
                if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
            ]
            if nested:
                # A def inside `if`/`with`/`try`: recurse so its body gets its own chain.
                found += _walk(
                    [s for s in ast.iter_child_nodes(statement) if isinstance(s, ast.stmt)], chain
                )
                continue
            found += [(call, chain, False) for call in _creation_sites(statement)]
    return found


def _sources() -> list[Path]:
    """**Every** Python file in the test tree — `conftest.py` and helpers included (`T260-R1`)."""
    return sorted(p for p in TESTS.rglob("*.py") if p.name not in EXEMPT)


def _unguarded(path: Path, source: str) -> list[str]:
    faults = []
    for call, chain, import_time in _walk(ast.parse(source).body, []):
        where = f"{path.name}:{call.lineno}"
        if import_time:
            faults.append(f"{where} creates a symlink at import time, before any fixture resolves")
        elif not chain:
            faults.append(f"{where} creates a symlink at module scope, where nothing can guard it")
        elif not any(_pytest_managed(f) and _requests(f, CAPABILITY) for f in chain):
            named = " -> ".join(f.name for f in chain)
            faults.append(
                f"{where} in {named}() creates a symlink with no pytest-managed ancestor "
                f"requesting `{CAPABILITY}`"
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

_UNGUARDED: Final = {
    "sync-test-attribute": "def test_x(tmp_path):\n    (tmp_path / 'l').symlink_to(tmp_path)\n",
    "os-attribute": "import os\ndef test_x(tmp_path):\n    os.symlink(tmp_path, tmp_path / 'l')\n",
    "direct-import": (
        "from os import symlink\ndef test_x(tmp_path):\n    symlink(tmp_path, tmp_path / 'l')\n"
    ),
    "async-test": "async def test_x(tmp_path):\n    (tmp_path / 'l').symlink_to(tmp_path)\n",
    "conftest-fixture": (
        "import pytest\n@pytest.fixture\ndef planted(tmp_path):\n"
        "    (tmp_path / 'l').symlink_to(tmp_path)\n    return tmp_path\n"
    ),
    "helper-function": (
        "def plant_a_symlink(tmp_path):\n    (tmp_path / 'l').symlink_to(tmp_path)\n"
    ),
    "module-scope": "from pathlib import Path\nPath('l').symlink_to(Path('.'))\n",
    "nested-helper": (
        "def test_x(tmp_path):\n    def inner():\n        (tmp_path / 'l').symlink_to(tmp_path)\n"
        "    inner()\n"
    ),
    # T260-R1's surviving case, verbatim: the helper takes a parameter *named* `symlinks`, and an
    # unguarded test calls it with None. pytest never resolved anything.
    "helper-named-parameter": (
        "def plant(path, symlinks):\n    path.symlink_to(path)\n\n"
        "def test_x(tmp_path):\n    plant(tmp_path, None)\n"
    ),
    "helper-defaulted-parameter": (
        "def plant(path, symlinks=None):\n    path.symlink_to(path)\n\n"
        "def test_x(tmp_path):\n    plant(tmp_path)\n"
    ),
    # Decorators and defaults run at import, before any fixture resolves.
    "decorator-expression": (
        "import pytest\nfrom pathlib import Path\n"
        "@pytest.mark.parametrize('x', [Path('l').symlink_to(Path('.'))])\n"
        "def test_x(x, symlinks):\n    pass\n"
    ),
    "parameter-default": (
        "from pathlib import Path\n"
        "def test_x(symlinks, planted=Path('l').symlink_to(Path('.'))):\n    pass\n"
    ),
}

_GUARDED: Final = {
    "sync-test": "def test_x(tmp_path, symlinks):\n    (tmp_path / 'l').symlink_to(tmp_path)\n",
    "async-test": (
        "async def test_x(tmp_path, symlinks):\n    (tmp_path / 'l').symlink_to(tmp_path)\n"
    ),
    "fixture-requesting-it": (
        "import pytest\n@pytest.fixture\ndef planted(tmp_path, symlinks):\n"
        "    (tmp_path / 'l').symlink_to(tmp_path)\n    return tmp_path\n"
    ),
    "keyword-only": (
        "def test_x(tmp_path, *, symlinks):\n    (tmp_path / 'l').symlink_to(tmp_path)\n"
    ),
    "closure-inside-a-guarded-test": (
        "def test_x(tmp_path, symlinks):\n    def plant():\n"
        "        (tmp_path / 'l').symlink_to(tmp_path)\n    plant()\n"
    ),
}


@pytest.mark.parametrize("spelling", sorted(_UNGUARDED), ids=sorted(_UNGUARDED))
def test_the_detector_catches_every_unguarded_spelling(spelling: str) -> None:
    """The mutations, run rather than described.

    **`T260-R1` found four of these undiscovered by the first version**: a `conftest.py` fixture, a
    helper in an ordinary module, `async def`, and `from os import symlink`. Each is a real route to
    the bare `WinError 1314` the task exists to remove, so each is a case here.
    """
    assert _unguarded(Path("probe.py"), _UNGUARDED[spelling]), (
        f"the detector does not see {spelling}, so the gate would pass while this spelling ships"
    )


@pytest.mark.parametrize("spelling", sorted(_GUARDED), ids=sorted(_GUARDED))
def test_the_detector_accepts_a_guarded_site(spelling: str) -> None:
    """The other direction, so the gate cannot pass by calling everything unguarded."""
    assert not _unguarded(Path("probe.py"), _GUARDED[spelling])
