"""Raw symlink creation is banned in the test tree; the capability object is the only route
(`T-260`).

**`T-070` built the guard and nothing made later tests use it.** On 2026-08-16, with
`SeCreateSymbolicLinkPrivilege` absent from `STARBASE`, five tests failed with a bare
`OSError: [WinError 1314]` while four that requested the `symlinks` fixture skipped cleanly
(CI run `31966531162`).

**Four review rounds tried to verify the fixture statically, and every round produced a
survivor.** The first gate read only synchronous `test_` bodies in `test_*.py`; then a parameter
merely *named* `symlinks` was shown to prove nothing (`plant(tmp_path, None)`); then a
`test_`-named function in an uncollected module and a home-grown `fixture` decorator; then a
*nested* `test_` function pytest never collects and `@hookimpl` counting because it was imported
from pytest. Each fix approximated more of pytest's collection and resolution semantics, and each
approximation had holes. **The approximation was the defect.**

So the maintainer authorized replacing the design (2026-08-17, `AGENTS.md` §10 — revisit the
design): the `symlinks` fixture now returns a `SymlinkCapability`, all creation goes through its
`.create()`, and this file enforces two flat rules that need no pytest semantics at all:

1. **No raw `symlink_to` / `symlink` call anywhere under `tests/`, except `capabilities.py`** —
   which *is* the probe. No context makes raw creation legal: not a fixture, not a guarded test,
   not a decorator, not module scope. One uniform rule, so the whole under-which-ancestor question
   those rounds fought about simply does not arise.
2. **`SymlinkCapability` is constructed only in `capabilities.py`.** Tests obtain it by requesting
   the fixture, which skips — naming the privilege — on a machine that cannot create symlinks.

What replaced the propagation question is a *runtime* property: a helper can take the capability as
a parameter, and a caller that fakes it with `None` fails loudly on **every** platform
(`AttributeError`), not silently with `[WinError 1314]` on an unprivileged Windows machine. That is
demonstrated below rather than claimed.

**A fifth finding followed the redesign**, and it is why the rules read as they do: ordinary
import aliases bypassed both — `from os import symlink as make_link` renames the local binding a
call-site ban is keyed on, and so does `SymlinkCapability as Cap`. **The import itself is banned
now**, under any alias, because the import is the one place the original name is still visible. The
exemption is also compared as an exact path, after a nested file named `capabilities.py` was found
to be silently exempt.

**The boundary, stated honestly** (per the `T-260` review's rulings): this prevents accidents. It
bans the raw Python spellings, their aliased imports, and the constructor call; it does not defend
against `__new__` forgery, assignment aliasing (`mk = os.symlink`), or shelling out to `ln -s`.
Those are accepted as out of scope — following bindings is the dataflow analysis this task spent
four rounds learning not to attempt. No current test does any of them, and one that started to
would be visible in review.
"""

import ast
from pathlib import Path
from typing import Final

import pytest

from tests.capabilities import SymlinkCapability

TESTS: Final = Path(__file__).resolve().parents[1]

#: The names that create a symlink, however they are reached: `path.symlink_to(...)`,
#: `os.symlink(...)`, or `symlink(...)` after `from os import symlink`. Matching names rather than
#: resolved callables flags an unrelated method that happens to be called `symlink` too — a false
#: positive costs one rename or one `.create()` call, a false negative costs a bare
#: `[WinError 1314]` on somebody's Windows machine.
RAW_CALLS: Final = frozenset({"symlink_to", "symlink"})

#: The capability class, whose *construction* is confined to the probe module.
CONSTRUCTOR: Final = SymlinkCapability.__name__

#: The one exempt file, **as a full path** — `tests/capabilities.py` exactly. The fifth review
#: found this was a basename comparison, which silently exempted *every* file named
#: `capabilities.py` anywhere under `tests/`; a nested one carrying raw creation passed the gate.
EXEMPT: Final = frozenset({Path("capabilities.py")})


def _calls(tree: ast.AST, names: frozenset[str]) -> list[ast.Call]:
    def matches(called: ast.expr) -> bool:
        if isinstance(called, ast.Attribute):
            return called.attr in names
        return isinstance(called, ast.Name) and called.id in names

    return [n for n in ast.walk(tree) if isinstance(n, ast.Call) and matches(n.func)]


def _import_bindings(tree: ast.AST, originals: frozenset[str]) -> dict[str, ast.ImportFrom]:
    """Every local name an `ImportFrom` binds to one of `originals`, aliased or not.

    The fifth review's surviving spelling: `from os import symlink as make_link` renames the
    *local* binding, so a call-site ban keyed on the original names never sees `make_link(...)`.
    The import is where the original name is still visible, so that is where it is read.
    """
    found: dict[str, ast.ImportFrom] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in originals:
                    found[alias.asname or alias.name] = node
    return found


def _sources() -> list[Path]:
    return sorted(p for p in TESTS.rglob("*.py") if p.relative_to(TESTS) not in EXEMPT)


def _raw_faults(path: Path, source: str) -> list[str]:
    """Raw creation, however spelled: attribute calls, direct-name calls, and aliased imports.

    **The import itself is banned**, not only calls through it: no file in the test tree has a
    sanctioned reason to import `symlink` under any name, because every raw call is banned anyway.
    Flagging the import gives the fault a line the author just wrote, and closes the
    imported-but-called-indirectly wriggle without any dataflow analysis.
    """
    tree = ast.parse(source)
    faults = []
    aliases = _import_bindings(tree, RAW_CALLS)
    for name, node in sorted(aliases.items()):
        faults.append(
            f"{path.name}:{node.lineno} imports raw symlink creation as `{name}` — banned "
            "however it is named"
        )
    for call in _calls(tree, RAW_CALLS | frozenset(aliases)):
        faults.append(f"{path.name}:{call.lineno} creates a symlink directly")
    return faults


def _construction_faults(path: Path, source: str) -> list[str]:
    """Construction of the capability, including through an aliased import of the class.

    A plain `from tests.capabilities import SymlinkCapability` stays legal — annotations need it —
    but an *aliased* import is flagged outright: annotations do not need a rename, and the alias
    is how a constructor call escapes a name-keyed ban.
    """
    tree = ast.parse(source)
    faults = []
    aliased = {
        name: node
        for name, node in _import_bindings(tree, frozenset({CONSTRUCTOR})).items()
        if name != CONSTRUCTOR
    }
    for name, node in sorted(aliased.items()):
        faults.append(
            f"{path.name}:{node.lineno} imports {CONSTRUCTOR} as `{name}` — the capability "
            "class may not be renamed"
        )
    for call in _calls(tree, frozenset({CONSTRUCTOR}) | frozenset(aliased)):
        faults.append(
            f"{path.name}:{call.lineno} constructs {CONSTRUCTOR} outside tests/capabilities.py"
        )
    return faults


def test_no_raw_symlink_creation_outside_the_capability_module() -> None:
    """Rule 1, over every Python file in the test tree with no context analysis at all.

    Anywhere means anywhere: module scope, fixtures, helpers, closures, decorators, defaults,
    `except` handlers, `match` arms, collected or not. Those rounds' survivors were all
    contexts a cleverer walker mis-classified; a flat ban has no contexts to mis-classify.
    """
    faults = [
        fault
        for path in _sources()
        for fault in _raw_faults(path, path.read_text(encoding="utf-8"))
    ]
    assert not faults, (
        "raw symlink creation is banned in tests (T-260):\n  "
        + "\n  ".join(faults)
        + "\nRequest the `symlinks` fixture and call symlinks.create(link, target) instead — it "
        "skips, naming the missing privilege, on a machine that cannot create symlinks."
    )


def test_the_capability_is_constructed_only_where_the_probe_lives() -> None:
    """Rule 2: the object exists only downstream of the skip-or-return fixture.

    Importing the name for a type annotation is fine and this file does it; *calling* the
    constructor elsewhere would mint the capability without the machine ever being asked.
    """
    faults = [
        fault
        for path in _sources()
        for fault in _construction_faults(path, path.read_text(encoding="utf-8"))
    ]
    assert not faults, (
        "the capability may only be constructed by the `symlinks` fixture (T-260):\n  "
        + "\n  ".join(faults)
    )


def test_this_gate_is_looking_at_something() -> None:
    """A rule that inspects nothing passes in silence, so both rules prove their subjects exist.

    The probe file must still contain raw creation — if `Path.symlink_to` is ever renamed, the ban
    list and the probe drift together or this fails. And the nine converted sites must still exist
    as `symlinks.create(...)` calls; if symlink coverage is deliberately removed, update the floor
    and say why.
    """
    probe = (TESTS / "capabilities.py").read_text(encoding="utf-8")
    raw_in_probe = _calls(ast.parse(probe), RAW_CALLS)
    assert len(raw_in_probe) == 2, (
        f"tests/capabilities.py holds {len(raw_in_probe)} raw creation sites, not the two the "
        "exemption exists for — `can_create_symlinks`'s probe and `SymlinkCapability.create`. "
        "A third raw site there is new machinery riding the exemption; fewer means the probe or "
        "the capability changed shape and the banned names may no longer be the ones that matter."
    )

    created = 0
    for path in _sources():
        for call in _calls(ast.parse(path.read_text(encoding="utf-8")), frozenset({"create"})):
            called = call.func
            if (
                isinstance(called, ast.Attribute)
                and isinstance(called.value, ast.Name)
                and called.value.id == "symlinks"
            ):
                created += 1
    assert created >= 9, (
        f"only {created} symlinks.create(...) sites remain; there were nine when this gate was "
        "written. If symlink coverage was deliberately removed, update this floor and say why."
    )
    assert len(_sources()) > 20, (
        f"the walk found only {len(_sources())} Python files under tests/, which suggests it is "
        "looking in the wrong place"
    )


# --- the detector, against every spelling the review rounds produced ----------------------------

#: Every context that defeated an earlier version of this gate, plus the base spellings. Under the
#: flat ban they are all the same case, which is the point of the redesign — but each stays here as
#: its own entry so a regression toward context-sensitivity fails loudly.
_RAW: Final = {
    "attribute-call": "def test_x(tmp_path):\n    (tmp_path / 'l').symlink_to(tmp_path)\n",
    "os-attribute": "import os\ndef test_x(tmp_path):\n    os.symlink(tmp_path, tmp_path / 'l')\n",
    "direct-import": (
        "from os import symlink\ndef test_x(tmp_path):\n    symlink(tmp_path, tmp_path / 'l')\n"
    ),
    "async-test": "async def test_x(tmp_path):\n    (tmp_path / 'l').symlink_to(tmp_path)\n",
    "module-scope": "from pathlib import Path\nPath('l').symlink_to(Path('.'))\n",
    "decorator-expression": (
        "import pytest\nfrom pathlib import Path\n"
        "@pytest.mark.parametrize('x', [Path('l').symlink_to(Path('.'))])\n"
        "def test_x(x):\n    pass\n"
    ),
    "parameter-default": (
        "from pathlib import Path\ndef test_x(planted=Path('l').symlink_to(Path('.'))):\n    pass\n"
    ),
    "except-handler": (
        "def test_x(tmp_path):\n    try:\n        pass\n    except ValueError:\n"
        "        (tmp_path / 'l').symlink_to(tmp_path)\n"
    ),
    "match-arm": (
        "def test_x(tmp_path, kind):\n    match kind:\n        case 'link':\n"
        "            (tmp_path / 'l').symlink_to(tmp_path)\n"
    ),
    "class-base-expression": (
        "from pathlib import Path\ndef base(x):\n    return object\n"
        "class Probe(base(Path('l').symlink_to(Path('.')))):\n    pass\n"
    ),
    # The survivors, one per review round. All flagged now, because context is irrelevant.
    "round-2-helper-named-parameter": (
        "def plant(path, symlinks):\n    path.symlink_to(path)\n\n"
        "def test_x(tmp_path):\n    plant(tmp_path, None)\n"
    ),
    "round-3-uncollected-test-function": (
        "def test_x(tmp_path, symlinks):\n    (tmp_path / 'l').symlink_to(tmp_path)\n"
    ),
    "round-3-home-grown-fixture": (
        "def fixture(fn):\n    return fn\n\n@fixture\ndef planted(tmp_path, symlinks):\n"
        "    (tmp_path / 'l').symlink_to(tmp_path)\n"
    ),
    "round-4-nested-test-function": (
        "def outer(tmp_path):\n    def test_inner(path, symlinks):\n"
        "        path.symlink_to(path)\n    return test_inner\n\n"
        "def test_x(tmp_path):\n    outer(tmp_path)(tmp_path, None)\n"
    ),
    "round-4-hookimpl": (
        "from pytest import hookimpl\n@hookimpl\ndef planted(tmp_path, symlinks):\n"
        "    (tmp_path / 'l').symlink_to(tmp_path)\n"
    ),
    # Even a genuine, correctly-guarded pytest fixture may not create one raw any more.
    "genuine-fixture-creating-raw": (
        "import pytest\n@pytest.fixture\ndef planted(tmp_path, symlinks):\n"
        "    (tmp_path / 'l').symlink_to(tmp_path)\n"
    ),
    # The fifth review's survivors: an ordinary import alias renames the local binding, so a
    # call-site ban keyed on the original names never fires. The import itself is banned now.
    "round-5-aliased-raw-import": (
        "from os import symlink as make_link\n"
        "def test_x(tmp_path):\n    make_link(tmp_path, tmp_path / 'l')\n"
    ),
    "round-5-aliased-import-uncalled": "from os import symlink as make_link\n",
}

_SANCTIONED: Final = {
    "test-via-capability": (
        "def test_x(tmp_path, symlinks):\n    symlinks.create(tmp_path / 'l', tmp_path)\n"
    ),
    "helper-passed-the-capability": (
        "def plant(tmp_path, symlinks):\n    symlinks.create(tmp_path / 'l', tmp_path)\n\n"
        "def test_x(tmp_path, symlinks):\n    plant(tmp_path, symlinks)\n"
    ),
    "closure-using-the-capability": (
        "def test_x(tmp_path, symlinks):\n    def plant():\n"
        "        symlinks.create(tmp_path / 'l', tmp_path)\n    plant()\n"
    ),
    "annotation-only": (
        "from tests.capabilities import SymlinkCapability\n"
        "def plant(tmp_path, symlinks: SymlinkCapability):\n"
        "    symlinks.create(tmp_path / 'l', tmp_path)\n"
    ),
}


def test_the_task_entry_states_the_case_counts_it_has() -> None:
    """`T260-R4`: the entry said sixteen while `_RAW` held eighteen.

    A hand-kept count beside a machine-checked table is the shape that produced the finding, so the
    count is derived here rather than trusted. Spelled in words because that is how the entry reads.
    """
    words = {
        4: "four",
        16: "sixteen",
        18: "eighteen",
        19: "nineteen",
        20: "twenty",
    }
    entry = (Path(__file__).resolve().parents[2] / "ai" / "TASKS.md").read_text(encoding="utf-8")
    section = entry[
        entry.index("### T-260 —") : entry.index("#### Out of scope", entry.index("### T-260 —"))
    ]
    raw, sanctioned = words.get(len(_RAW)), words.get(len(_SANCTIONED))
    assert raw and sanctioned, f"add {len(_RAW)}/{len(_SANCTIONED)} to the words table"
    assert f"**{raw.capitalize()}** parametrized raw spellings" in section, (
        f"T-260's evidence does not state {raw} raw spellings"
    )
    assert f"{sanctioned} sanctioned shapes" in section, (
        f"T-260's evidence does not state {sanctioned} sanctioned shapes"
    )


@pytest.mark.parametrize("spelling", sorted(_RAW), ids=sorted(_RAW))
def test_every_raw_spelling_is_flagged(spelling: str) -> None:
    """The mutations of every review round, kept as the definition of what banned means."""
    assert _raw_faults(Path("probe.py"), _RAW[spelling]), (
        f"the ban does not see {spelling}, so that spelling would ship"
    )


def test_the_construction_ban_sees_the_aliased_class_import() -> None:
    """The fifth review's other survivor: rename the class on import, construct under the alias."""
    source = (
        "from tests.capabilities import SymlinkCapability as Cap\n"
        "def test_x(tmp_path):\n    Cap().create(tmp_path / 'l', tmp_path)\n"
    )
    faults = _construction_faults(Path("probe.py"), source)
    assert len(faults) == 2, faults  # the import, and the call through it


@pytest.mark.parametrize("spelling", sorted(_SANCTIONED), ids=sorted(_SANCTIONED))
def test_the_sanctioned_route_is_not_flagged(spelling: str) -> None:
    source = _SANCTIONED[spelling]
    assert not _raw_faults(Path("probe.py"), source)
    assert not _construction_faults(Path("probe.py"), source)


def test_forging_the_capability_with_none_fails_loudly_on_every_platform() -> None:
    """The runtime property that dissolved the propagation question.

    Under the old design, a helper taking a parameter named `symlinks` could be called with `None`
    and reach raw creation — failing only on an unprivileged Windows machine, as a bare
    `[WinError 1314]`. Under this design the same forgery breaks immediately, everywhere, with a
    name in the message.
    """

    def plant(link: Path, symlinks: SymlinkCapability) -> None:
        symlinks.create(link, link)

    with pytest.raises(AttributeError, match="create"):
        plant(Path("never-created"), None)  # type: ignore[arg-type]


def test_the_construction_ban_sees_both_spellings() -> None:
    flagged = _construction_faults(
        Path("probe.py"),
        "from tests.capabilities import SymlinkCapability\ncap = SymlinkCapability()\n",
    )
    assert flagged, "direct construction was not flagged"
    flagged = _construction_faults(
        Path("probe.py"),
        "import tests.capabilities as cap\nc = cap.SymlinkCapability()\n",
    )
    assert flagged, "attribute-form construction was not flagged"
