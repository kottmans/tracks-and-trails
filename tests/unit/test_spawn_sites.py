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

**The rule is syntactic, and `T258-R8` is why that is written down here rather than left to be
discovered.** The first version matched one shape — a plain `ast.Assign` binding a `Process(...)`
call to a name, then `name.start()` — so two ordinary spellings walked past it: an **annotated**
assignment (`child: Process = context.Process(...)`), because that is an `ast.AnnAssign` and not an
`ast.Assign` at all, and an **inline** start (`context.Process(...).start()`), which binds no name
to look up. Both are caught below, and `test_the_gate_catches_every_supported_spelling` fails if
either stops being.

**What this cannot see, stated as a limit rather than implied to be covered:** anything that puts a
process behind a value the scan would have to *follow* — a factory function returning one, an
alias (`spawn = context.Process`), a process held in a list or a dictionary, a `getattr` call.
Following those is data-flow analysis, which this is not and does not claim to be.
`test_the_rule_s_boundary_is_a_fact_not_a_claim` asserts the escape rather than describing it, so
the limit cannot quietly widen. The behavioural half of the guarantee is what covers the rest:
`start_contained` refuses at run time whatever spelling reached it.
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


def _builds_a_process(node: ast.AST) -> bool:
    """Whether one node is a `Process(...)` or `something.Process(...)` call.

    Matched on the attribute or name alone. A stricter rule would have to resolve what
    `context` is, which is the data-flow analysis this file says it does not do.
    """
    if not isinstance(node, ast.Call):
        return False
    function = node.func
    name = function.attr if isinstance(function, ast.Attribute) else getattr(function, "id", "")
    return name == "Process"


def _process_variables(tree: ast.AST) -> set[str]:
    """Names bound to a `…Process(…)` call anywhere in one module.

    **Both assignment forms** (`T258-R8`): `child = context.Process(...)` is an `ast.Assign` with
    a list of targets, and `child: Process = context.Process(...)` is an `ast.AnnAssign` with
    exactly one — a different node type that the first version of this scan never looked at, so an
    annotation was enough to leave the module unguarded.
    """
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets: list[ast.expr] = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if node.value is None or not _builds_a_process(node.value):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                bound.add(target.id)
    return bound


def _starts_a_process_it_built(tree: ast.AST, variables: set[str]) -> list[int]:
    """Line numbers of `.start()` calls this module makes on a process of its own.

    Two spellings, and the second is why this is a function rather than one loop
    (`T258-R8`): `child.start()` on a name the module bound, and
    `context.Process(...).start()` **inline**, which binds no name at all and so cannot be found
    by looking one up.
    """
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if not isinstance(function, ast.Attribute) or function.attr != "start":
            continue
        receiver = function.value
        named = isinstance(receiver, ast.Name) and receiver.id in variables
        if named or _builds_a_process(receiver):
            lines.append(node.lineno)
    return lines


def _offenders_in(source: str) -> list[int]:
    """The whole rule over one piece of source, so a mutation can be written as a string.

    The mutation tests below need to ask *"would the gate catch this?"* about code that does not
    exist in the tree. Running the rule over a string is the only way to ask that without writing
    an offending spawn site into `src/` and hoping the test remembers to remove it.
    """
    tree = ast.parse(source)
    return _starts_a_process_it_built(tree, _process_variables(tree))


def _modules_that_spawn() -> dict[str, tuple[ast.AST, set[str]]]:
    found: dict[str, tuple[ast.AST, set[str]]] = {}
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if not any(_builds_a_process(node) for node in ast.walk(tree)):
            continue
        found[path.relative_to(SOURCE_ROOT).as_posix()] = (tree, _process_variables(tree))
    return found


def test_the_scan_finds_the_spawn_sites_it_is_meant_to_guard() -> None:
    """The positive control: a rule that matches nothing passes for the wrong reason.

    `ai/TESTING.md`'s instrument rule, applied to a static check. If `_builds_a_process` stopped
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
        offenders += [
            f"{module}:{line} — a process this module built is started here"
            for line in _starts_a_process_it_built(tree, variables)
        ]

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


#: The three spellings the rule supports, each written as the mutation it is: source that a future
#: spawn site could plausibly contain, and that must not pass. Named individually so a failure
#: says *which* spelling stopped being caught rather than that "the scan" broke.
SUPPORTED_SPELLINGS = {
    "direct": (
        "import multiprocessing\n"
        "context = multiprocessing.get_context('spawn')\n"
        "child = context.Process(target=work)\n"
        "child.start()\n"
    ),
    "annotated": (
        "import multiprocessing\n"
        "from multiprocessing.context import SpawnProcess\n"
        "context = multiprocessing.get_context('spawn')\n"
        "child: SpawnProcess = context.Process(target=work)\n"
        "child.start()\n"
    ),
    "inline": (
        "import multiprocessing\n"
        "multiprocessing.get_context('spawn').Process(target=work).start()\n"
    ),
}


def test_the_gate_catches_every_supported_spelling() -> None:
    """`T258-R8`, as three mutations rather than as a claim about coverage.

    Two of these passed the first version of the rule. The annotated form is an `ast.AnnAssign`,
    which the scan never looked at; the inline form binds no name, so a scan that works by
    collecting names and then looking them up has nothing to look up. Either was enough to put a
    new spawn site into the tree with a green gate over it.
    """
    missed = [name for name, source in SUPPORTED_SPELLINGS.items() if not _offenders_in(source)]

    assert not missed, (
        f"the gate no longer catches these spellings of an uncontained spawn: {missed}. "
        "Each is a way a future spawn site could start a child without `start_contained`, and "
        "each is why this rule reads more node types than the obvious one."
    )


def test_the_gate_does_not_fire_on_the_contained_spelling() -> None:
    """The other side of the same instrument: a rule that flags everything proves nothing.

    `start_contained(child)` is what every site is supposed to look like, and it must come back
    clean — including in the annotated and inline forms, where an over-eager match on the word
    `start` would fire on the seam itself.
    """
    contained = (
        "import multiprocessing\n"
        "from tracks_and_trails.downloader import process_tree\n"
        "from multiprocessing.context import SpawnProcess\n"
        "context = multiprocessing.get_context('spawn')\n"
        "child: SpawnProcess = context.Process(target=work)\n"
        "process_tree.start_contained(child)\n"
        "process_tree.start_contained(context.Process(target=work))\n"
    )

    assert not _offenders_in(contained), (
        "the gate flagged a spawn site that goes through `start_contained`, which would make the "
        "rule impossible to satisfy and therefore the first thing a future author disables"
    )


def test_the_rule_s_boundary_is_a_fact_not_a_claim() -> None:
    """The limit, asserted rather than described (`T-263`).

    A factory or an alias puts the process behind a value this scan would have to *follow*, and
    following values is data-flow analysis. **This test asserts that those escape**, so the
    boundary in the module docstring stays true: if somebody later widens the rule to cover them,
    this fails and the docstring gets corrected in the same change rather than three months later.

    What covers the escapes is not this file. `start_contained` refuses at run time whatever
    spelling reached it, and `test_process_tree.py` is where that is measured — a static rule and
    a behavioural refusal, each doing the half the other cannot.
    """
    escapes = {
        "factory": (
            "import multiprocessing\n"
            "def build():\n"
            "    return multiprocessing.get_context('spawn').Process(target=work)\n"
            "build().start()\n"
        ),
        "alias": (
            "import multiprocessing\n"
            "spawn = multiprocessing.get_context('spawn').Process\n"
            "child = spawn(target=work)\n"
            "child.start()\n"
        ),
    }

    caught = [name for name, source in escapes.items() if _offenders_in(source)]

    assert not caught, (
        f"these now fail the static gate: {caught}. That is an improvement, not a defect — but "
        "the module docstring names them as escapes this rule cannot see, and a limit that has "
        "stopped being true has to stop being written down. Update both together."
    )
