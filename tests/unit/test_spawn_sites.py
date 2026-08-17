"""Every product-owned process starts through one seam (`T-258`, `T258-R3`).

**Why this is a static test and not a behavioural one.** The window `T-258` is about opens before
the child's target is unpickled, so the child cannot know what it was going to be, and no test of
one spawn *path* can cover the class. `T258-R3` found exactly that: the manager's spawn was
contained on the day the fix landed, while `ytdlp_resolution.resolve_in_a_child` and
`_freeze_probe.run_probe` — both product-owned, both shipped — were not. The five orphaned command
lines carry no target identity, so nothing in the record even establishes that they came through
the manager.

What reopens the class is **a new spawn site**, written months from now by somebody who has not
read this. A behavioural test cannot see one that does not exist yet; a rule over the source can.

**The rule:** if a module builds a `multiprocessing` process, it must not call `.start()` on it.
`process_tree.start_contained()` is the only way, and it establishes the outer Job before the
process exists and raises rather than proceeding when it cannot.
"""

from __future__ import annotations

import ast
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "tracks_and_trails"

#: The three product-owned spawn sites as of `T-258`. Named so this test **fails when a fourth
#: appears** rather than silently covering it — a new site is exactly the event the rule exists
#: for, and it deserves a person reading this file rather than a green tick.
KNOWN_SPAWN_SITES = {
    "downloader/manager.py",
    "downloader/ytdlp_resolution.py",
    "_freeze_probe.py",
}


def _process_variables(tree: ast.AST) -> set[str]:
    """Names bound to a `…Process(…)` call anywhere in one module."""
    bound: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        call = node.value
        if not isinstance(call, ast.Call):
            continue
        function = call.func
        name = function.attr if isinstance(function, ast.Attribute) else getattr(function, "id", "")
        if name != "Process":
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                bound.add(target.id)
    return bound


def _modules_that_spawn() -> dict[str, tuple[ast.AST, set[str]]]:
    found: dict[str, tuple[ast.AST, set[str]]] = {}
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        variables = _process_variables(tree)
        if variables:
            found[path.relative_to(SOURCE_ROOT).as_posix()] = (tree, variables)
    return found


def test_the_scan_finds_the_spawn_sites_it_is_meant_to_guard() -> None:
    """The positive control: a rule that matches nothing passes for the wrong reason.

    `ai/TESTING.md`'s instrument rule, applied to a static check. If `_process_variables` stopped
    recognising `context.Process(...)` — a refactor to a factory function would do it — every
    assertion below would pass over an empty set and this file would report a guarantee it was no
    longer checking.
    """
    spawning = _modules_that_spawn()

    assert set(spawning) == KNOWN_SPAWN_SITES, (
        f"the set of modules that construct a multiprocessing process changed: {set(spawning)}. "
        "If a new spawn site was added, it must start through `process_tree.start_contained` "
        "and be named here; if one was removed, drop it from KNOWN_SPAWN_SITES."
    )


def test_no_module_starts_a_process_it_built() -> None:
    """`T258-R3`: `.start()` on a process object is the call that reopens the window."""
    offenders: list[str] = []
    for module, (tree, variables) in _modules_that_spawn().items():
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "start"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in variables
            ):
                offenders.append(f"{module}:{node.lineno} — {node.func.value.id}.start()")

    assert not offenders, (
        "these call `.start()` directly on a process they built, which spawns a child into the "
        "pre-bootstrap window with no outer containment:\n  "
        + "\n  ".join(offenders)
        + "\nUse `process_tree.start_contained(process)`, which establishes the Job object first "
        "and refuses rather than spawning when it cannot."
    )


def test_every_spawn_site_reaches_the_seam() -> None:
    """The other half: not calling `.start()` is not the same as calling the right thing.

    A module could satisfy the test above by never starting its process at all, which would be a
    different defect with the same green tick.
    """
    missing = [
        module
        for module in _modules_that_spawn()
        if "start_contained" not in (SOURCE_ROOT / module).read_text(encoding="utf-8")
    ]

    assert not missing, f"these build a process but never reach `start_contained`: {missing}"
