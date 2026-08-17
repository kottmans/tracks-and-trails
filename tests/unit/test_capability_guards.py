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


def _functions(tree: ast.AST) -> list[_Function]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]


def _creation_sites(tree: ast.AST) -> list[ast.Call]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call) and _is_creation(n)]


def _enclosing(tree: ast.AST, call: ast.Call) -> list[_Function]:
    """Every function containing `call`, outermost first. Empty if it sits at module scope.

    **The whole chain, not the innermost** (`T260-R1`'s correction, corrected once more by running
    it): a closure defined inside a guarded test is itself guarded, because the test skips before
    the closure can run. `test_a_symlink_planted_during_the_mkdir_is_still_caught` has exactly that
    shape — it patches `Path.mkdir` with a local function that plants the link — and requiring the
    *innermost* function to carry the fixture flagged it wrongly.

    A helper at module level with no guarded ancestor still fails, which is the case that matters.
    """
    return [f for f in _functions(tree) if any(node is call for node in ast.walk(f))]


def _sources() -> list[Path]:
    """**Every** Python file in the test tree — `conftest.py` and helpers included (`T260-R1`)."""
    return sorted(p for p in TESTS.rglob("*.py") if p.name not in EXEMPT)


def _unguarded(path: Path, source: str) -> list[str]:
    tree = ast.parse(source)
    faults = []
    for call in _creation_sites(tree):
        chain = _enclosing(tree, call)
        where = f"{path.name}:{call.lineno}"
        if not chain:
            faults.append(f"{where} creates a symlink at module scope, where nothing can guard it")
        elif not any(_requests(f, CAPABILITY) for f in chain):
            named = " -> ".join(f.name for f in chain)
            faults.append(f"{where} in {named}() creates a symlink without `{CAPABILITY}`")
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
    "helper-taking-it": (
        "def plant(tmp_path, symlinks):\n    (tmp_path / 'l').symlink_to(tmp_path)\n"
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
