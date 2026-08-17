"""A test that needs a platform capability must ask for it (`T-260`).

**`T-070` built the guard and nothing made later tests use it.** That task found four tests failing
on an ordinary Windows desktop with a bare `OSError` naming no cause, added
`tests.capabilities.can_create_symlinks` and the `symlinks` fixture that skips with a message a
person can act on, and fixed the four. Tests written afterwards did not request it — and on
2026-08-16, with `SeCreateSymbolicLinkPrivilege` absent from `STARBASE`, **five of them failed with
`OSError: [WinError 1314]` while the four that had the fixture skipped cleanly** (CI run
`31966531162`).

**So the fix is the property rather than the five.** `T-070` fixed a list; this fails any test that
creates a symlink without asking whether the machine can. The list was never the defect — nothing
made the next one join it.

**Why static rather than a runtime `except OSError`.** Catching the error at runtime would convert
every future privilege failure into a silent pass, which is worse than the bare `OSError` this
started with: a skip that nobody sees is indistinguishable from coverage. This walks the source, so
it fails at the moment the test is written, on any machine, whether or not the capability happens
to be present. That matters here — Developer Mode is now enabled on `STARBASE`, so the five would
pass again and the gap would be invisible.
"""

import ast
from pathlib import Path
from typing import Final

import pytest

TESTS: Final = Path(__file__).resolve().parents[1]

#: The fixture a symlink-creating test must request (`tests/capabilities.py`).
CAPABILITY: Final = "symlinks"

#: How a test creates a symlink. Attribute names rather than full expressions, because the call may
#: be written as `path.symlink_to(...)`, `os.symlink(...)` or `Path(...).symlink_to(...)`.
SYMLINK_CALLS: Final = frozenset({"symlink_to", "symlink"})

#: `tests/capabilities.py` defines the probe and is allowed to create one without asking itself.
EXEMPT: Final = frozenset({"capabilities.py"})


def _creates_a_symlink(node: ast.FunctionDef) -> bool:
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr in SYMLINK_CALLS
        for child in ast.walk(node)
    )


def _requests(node: ast.FunctionDef, fixture: str) -> bool:
    arguments = node.args
    names = [a.arg for a in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)]
    return fixture in names


def _symlink_tests() -> list[tuple[Path, ast.FunctionDef]]:
    found = []
    for path in sorted(TESTS.rglob("test_*.py")):
        if path.name in EXEMPT:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.FunctionDef)
                and node.name.startswith("test_")
                and _creates_a_symlink(node)
            ):
                found.append((path, node))
    return found


def test_every_test_that_creates_a_symlink_asks_whether_it_can() -> None:
    """The rule `T-070` could not enforce, enforced.

    A test that creates a symlink without the `symlinks` fixture fails with a bare `OSError` on any
    machine lacking the privilege — which is the ordinary state of a Windows desktop, not an
    unusual one. With the fixture it skips, naming the privilege.
    """
    unguarded = [
        f"{path.relative_to(TESTS)}::{node.name}"
        for path, node in _symlink_tests()
        if not _requests(node, CAPABILITY)
    ]
    assert not unguarded, (
        "these create a symlink and never ask whether the machine can, so they fail with a bare "
        f"OSError [WinError 1314] rather than skipping: {unguarded}. Add the `{CAPABILITY}` "
        "fixture from tests/capabilities.py."
    )


def test_this_gate_is_looking_at_something() -> None:
    """A rule that inspects nothing passes in silence, so it says how much it inspected.

    Nine tests created a symlink when this was written — three in `tests/unit/test_paths.py`, six in
    `tests/integration/test_worker.py`. If that reaches zero the symlink coverage has gone, not the
    risk.
    """
    found = _symlink_tests()
    assert len(found) >= 9, (
        f"only {len(found)} tests create a symlink; there were nine when this gate was written. "
        "If symlink coverage was deliberately removed, update this floor and say why."
    )


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            "def test_x(tmp_path):\n    (tmp_path / 'l').symlink_to(tmp_path)\n", id="path"
        ),
        pytest.param("def test_x(tmp_path):\n    os.symlink(tmp_path, tmp_path / 'l')\n", id="os"),
    ],
)
def test_the_detector_sees_both_spellings(source: str) -> None:
    """The mutation, run rather than described: an unguarded test of each spelling is detected.

    `T-070`'s lesson was that a list is not a property. This asserts the *detector* works, so the
    gate above cannot pass by failing to recognise a symlink call.
    """
    node = next(
        n
        for n in ast.walk(ast.parse(source))
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    )
    assert _creates_a_symlink(node)
    assert not _requests(node, CAPABILITY)


def test_the_detector_accepts_a_guarded_test() -> None:
    """The other direction, so the gate cannot pass by calling everything guarded."""
    source = "def test_x(tmp_path, symlinks):\n    (tmp_path / 'l').symlink_to(tmp_path)\n"
    node = next(
        n
        for n in ast.walk(ast.parse(source))
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    )
    assert _creates_a_symlink(node)
    assert _requests(node, CAPABILITY)
