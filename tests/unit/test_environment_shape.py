"""The premise `OPS-008` rests on, guarded (`T-098`).

`OPS-008` decided not to close the three blind spots in `T-044`'s environment ownership gate. The
load-bearing reason was a measurement rather than an intuition: **all three are structurally
unreachable in the module the gate protects.** Each needs a specific construct to exist at all,
and `downloader/environment.py` contains none of them.

| Gap | Construct it requires | Measured 2026-07-30 |
|---|---|---|
| An export behind a guard false at run time | a module-scope `if` | 0 |
| A name imported and then rebound by a fallback | a module-scope `try`/`except` | 0 |
| Dynamic rebinding of an imported name | `globals`/`setattr`/`exec`/… | 0 |

**Nothing enforced that.** Adding a platform branch to a module that resolves paths across two
operating systems is an ordinary thing to do. It would make the first gap live, nothing would
fail, and `OPS-008` would be silently obsolete.

## This is not a sixth attempt at the gaps

`T044-R1` was found six times. Every fix that tried to close a gap parsed for **bindings** and was
defeated by binding syntax its author had not enumerated. This parses for the three **constructs
the gaps require** — a closed set that follows from the gaps' own definitions rather than from
Python's grammar.

And it fails in the safe direction. If the set is ever incomplete, the missing construct simply
does not appear, the assertion still holds, and the gate is unchanged. An enumeration that is
wrong here costs a warning nobody gets; an enumeration that was wrong in the five previous
attempts cost a guarantee that was claimed and untrue.

**A failure here means "revisit `OPS-008`", not "fix the module."** Adding one of these constructs
is allowed. What is not allowed is adding one while a decision that assumed their absence stays on
the books.
"""

import ast
from pathlib import Path

import pytest

MODULE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "tracks_and_trails"
    / "downloader"
    / "environment.py"
)

#: Namespace manipulation that could rebind an imported name out from under the gate's parse.
DYNAMIC_CALLS = frozenset({"globals", "locals", "setattr", "vars", "exec", "eval"})

#: What `OPS-008` measured module scope to contain. Anything else is a shape the decision did not
#: consider — see `test_the_module_scope_is_still_the_shape_ops_008_measured`.
EXPECTED_AT_MODULE_SCOPE = frozenset(
    {"Expr", "Import", "ImportFrom", "AnnAssign", "Assign", "FunctionDef", "ClassDef"}
)

REVISIT = "Revisit OPS-008 rather than assuming this test is wrong."


def tree() -> ast.Module:
    return ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))


def test_the_module_is_where_the_decision_says_it_is() -> None:
    """Every assertion below is vacuous if the path is wrong."""
    assert MODULE.is_file(), f"{MODULE} does not exist; OPS-008's premise cannot be checked"


def test_no_module_scope_guard_makes_the_first_gap_reachable() -> None:
    """Gap 1 needs a conditional at module scope. There is none, so nothing hides behind one.

    A guard **inside a function** is irrelevant and deliberately not reported: the gate compares
    the module's namespace against its imports, and only a module-scope binding can be conditional
    in the way that matters.
    """
    guards = [node for node in tree().body if isinstance(node, ast.If)]
    lines = [node.lineno for node in guards]
    assert not guards, (
        f"module-scope `if` at line(s) {lines}. An export behind a guard that is false at run "
        f"time is invisible to T-044's gate, so OPS-008's first blind spot is reachable. {REVISIT}"
    )


def test_no_import_fallback_makes_the_second_gap_reachable() -> None:
    """Gap 2 needs `try: from x import Y / except ImportError: Y = ...` at module scope.

    This is the plausible one — an optional dependency is ordinary code — which is why it gets a
    named test rather than a note.
    """
    attempts = [node for node in tree().body if isinstance(node, ast.Try)]
    lines = [node.lineno for node in attempts]
    assert not attempts, (
        f"module-scope `try` at line(s) {lines}. A name imported and then rebound by a fallback is "
        f"subtracted by the gate's import parse while the fallback bound it. {REVISIT}"
    )


def test_no_dynamic_namespace_call_makes_the_third_gap_reachable() -> None:
    """Gap 3 needs `globals()["Path"] = ...` or a relative.

    Checked anywhere rather than at module scope only: a function called during import reaches the
    same namespace.
    """
    found = [
        (node.func.id, node.lineno)
        for node in ast.walk(tree())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in DYNAMIC_CALLS
    ]
    assert not found, (
        f"dynamic namespace calls {found}. An imported name rebound this way is subtracted by the "
        f"gate's parse while pointing at something else. {REVISIT}"
    )


def test_the_module_scope_is_still_the_shape_ops_008_measured() -> None:
    """The positive form of the three above, so a *new kind* of construct is noticed too.

    Each test above names a construct. This one says what the module **is**. A module-scope `with`,
    `match`, `for` or `while` would pass all three and still be a shape `OPS-008` never considered,
    and the honest response to that is to look again rather than to assume the list was complete.
    """
    kinds = {type(node).__name__ for node in tree().body}
    unexpected = sorted(kinds - EXPECTED_AT_MODULE_SCOPE)
    assert not unexpected, (
        f"module scope now contains {unexpected}, which OPS-008's measurement did not cover. That "
        f"is not necessarily a blind spot, but it is a shape the decision did not consider. "
        f"{REVISIT}"
    )


@pytest.mark.parametrize(
    ("gap", "construct"),
    [
        ("guard", "if TYPE_CHECKING:\n    X = 1\n"),
        ("fallback", "try:\n    from json import loads\nexcept ImportError:\n    loads = None\n"),
        ("dynamic", "globals()['Path'] = None\n"),
    ],
)
def test_each_construct_is_actually_detected(gap: str, construct: str) -> None:
    """`docs/project/TESTING.md` §13: a guard nobody has watched fail is not evidence.

    The three tests above read the real module, which is clean, so on its own each has never fired.
    These put the construct through the same detection and prove it is seen.
    """
    parsed = ast.parse(construct)
    if gap == "guard":
        assert any(isinstance(node, ast.If) for node in parsed.body)
    elif gap == "fallback":
        assert any(isinstance(node, ast.Try) for node in parsed.body)
    else:
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in DYNAMIC_CALLS
            for node in ast.walk(parsed)
        )
