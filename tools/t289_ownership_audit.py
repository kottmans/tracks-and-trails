"""Where could the product ever leave a widget for the collector? Read `src/` and say.

**Why a reading and not another measurement** (`T-289`, criterion 2). Five probes have now asked
*"is there a collectable product widget at this instant?"* — the watch over 60 isolated sessions and
two real-display runs, and the forced probe at two sampled moments — and every answer has been no.
That question has a regress in it: another null sample cannot separate *there is none* from *we
sampled the wrong instant*, which is what `T289-R14`…`R20` kept finding in the instruments rather
than in the product.

This asks the complementary question, which has an end. **A widget can only be owned by Python if
the product leaves it without a Qt parent**, because a parent makes the C++ object Qt's and dropping
the wrapper then destroys nothing (`ai/TESTING.md` §7). So every construction site is enumerated and
each is either given a parent or it is not. The ones that are not are the entire candidate list, and
they are few enough to read.

**Two doors into Python ownership, and this checks both**: construction without a parent, and
un-parenting afterwards — `setParent(None)`, `takeWidget()`, `removeWidget()`, `takeAt()`, which
hand the C++ object back.

## What it cannot see, stated rather than discovered

- **Widgets library code constructs.** Qt makes its own — a session's `QMenu`s and `QFrame`s are
  Qt's, not this file's — and no scan of `src/` finds them. The runtime survey in `T-289` covers
  that gap by asking `QApplication.topLevelWidgets()`, which *is* the set of parentless widgets.
- **A name is not a type.** Classes are resolved by name; a shadowed or aliased widget class would
  be classified by the name at the call site.
- **A product class with no `__init__` of its own** inherits Qt's, so Qt's rule is applied to it.
  Both such cases in this tree were read by hand and do pass a parent.
- It says where a widget *could* be Python-owned. Whether one is, at a given moment, is what the
  probes measure.

    tools/t289_ownership_audit.py --self-test
    tools/t289_ownership_audit.py
"""

from __future__ import annotations

import argparse
import ast
import sys
import tempfile
from pathlib import Path
from typing import Final

SRC: Final = Path("src/tracks_and_trails")

#: Imported from `QtWidgets` but not widgets: nothing here has a parent to be owned by.
NOT_A_WIDGET: Final = frozenset(
    {
        "QApplication",
        "QStyle",
        "QStyleFactory",
        "QSystemTrayIcon",
        "QCompleter",
        "QDataWidgetMapper",
        "QGraphicsEffect",
        "QGraphicsDropShadowEffect",
        "QStyledItemDelegate",
        "QAbstractItemDelegate",
        "QItemDelegate",
        "QFileIconProvider",
        "QSizePolicy",
        "QStyleOptionViewItem",
    }
)

#: The calls that hand a C++ widget back to Python after it was parented.
UNPARENTING: Final = ("setParent", "takeWidget", "takeItem", "removeWidget", "takeAt")


def qt_widget_names(trees: dict[Path, ast.Module]) -> set[str]:
    """Every `QtWidgets` name the product imports, minus the ones that are not widgets."""
    names: set[str] = set()
    for tree in trees.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "QtWidgets" in node.module:
                names.update(alias.name for alias in node.names if alias.name.startswith("Q"))
    names -= NOT_A_WIDGET
    # A layout is a `QObject`, not a widget, and a `QStyleOption*` is a plain value class with no
    # parent at all. Neither can be the `~QWidget` the core dump names.
    return {
        name
        for name in names
        if not name.endswith("Layout") and not name.startswith("QStyleOption")
    }


def product_widget_names(trees: dict[Path, ast.Module], qt: set[str]) -> set[str]:
    """Product classes that are widgets, resolved transitively through their own base classes."""
    bases: dict[str, list[str]] = {}
    for tree in trees.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases[node.name] = [b.id for b in node.bases if isinstance(b, ast.Name)] + [
                    b.attr for b in node.bases if isinstance(b, ast.Attribute)
                ]
    widgets: set[str] = set()
    growing = True
    while growing:
        growing = False
        for name, parents in bases.items():
            if name not in widgets and any(p in qt or p in widgets for p in parents):
                widgets.add(name)
                growing = True
    return widgets


def own_initialisers(trees: dict[Path, ast.Module], product: set[str]) -> dict[str, list[str]]:
    """Each product widget's own `__init__` parameters, when it defines one."""
    signatures: dict[str, list[str]] = {}
    for tree in trees.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in product:
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                        signatures[node.name] = [a.arg for a in item.args.args][1:] + [
                            a.arg for a in item.args.kwonlyargs
                        ]
    return signatures


def is_parented(
    call: ast.Call, name: str, product: set[str], signatures: dict[str, list[str]]
) -> bool:
    """Whether this construction gives the widget a Qt parent.

    **A positional argument is not automatically a parent**, which the first version assumed:
    `QLabel("text")` has one and is parentless. Qt's convention is that `parent` comes last and a
    literal is never one. For a product class that declares its own `__init__` the question is
    asked exactly, against that signature.
    """
    if any(keyword.arg == "parent" for keyword in call.keywords):
        return True
    if name in product and name in signatures:
        parameters = signatures[name]
        return "parent" in parameters and len(call.args) > parameters.index("parent")
    return bool(call.args) and not isinstance(call.args[-1], ast.Constant)


def audit(root: Path) -> tuple[list[tuple[str, int, str, str]], int, list[tuple[str, int, str]]]:
    """Return the parentless construction sites, the total, and any un-parenting calls."""
    trees = {path: ast.parse(path.read_text()) for path in sorted(root.rglob("*.py"))}
    qt = qt_widget_names(trees)
    product = product_widget_names(trees, qt)
    signatures = own_initialisers(trees, product)
    every = qt | product

    parentless: list[tuple[str, int, str, str]] = []
    unparenting: list[tuple[str, int, str]] = []
    total = 0
    for path, tree in trees.items():
        lines = path.read_text().splitlines()
        relative = str(path).replace(f"{root}/", "")
        for node in ast.walk(tree):
            hands_it_back = isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            if hands_it_back and node.func.attr in UNPARENTING:  # type: ignore[union-attr]
                unparenting.append((relative, node.lineno, lines[node.lineno - 1].strip()))
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            name = node.func.id
            if name not in every:
                continue
            total += 1
            if not is_parented(node, name, product, signatures):
                parentless.append((relative, node.lineno, name, lines[node.lineno - 1].strip()))
    return parentless, total, unparenting


SELF_TEST_SOURCE: Final = """
from PySide6.QtWidgets import QLabel, QWidget

class Panel(QWidget):
    def __init__(self, jobs, parent=None):
        super().__init__(parent)

def build():
    loose = QLabel("just text")          # parentless: a literal is not a parent
    titled = QLabel("text", loose)       # parented: last positional is a widget
    keyword = QLabel("text", parent=loose)
    orphan = Panel(jobs=None)            # parentless: its own signature says so
    adopted = Panel(None, loose)         # parented: positional lands on `parent`
    inherited = QWidget(loose)
    loose.setParent(None)                # an un-parenting call
    return titled, keyword, orphan, adopted, inherited
"""


def self_test() -> int:
    """Classify a fixture whose answers are known, because a scanner that finds nothing looks calm.

    Four of the six constructions below are parented and two are not, and the reader can see which
    by looking. An earlier version of this scan called `QLabel("text")` parented — a false negative,
    which for this instrument is the dangerous direction: it hides candidates and reports an empty
    list that looks like an answer.
    """
    with tempfile.TemporaryDirectory(prefix="t289-audit-") as directory:
        fixture = Path(directory)
        (fixture / "sample.py").write_text(SELF_TEST_SOURCE)
        parentless, total, unparenting = audit(fixture)
    found = {(name, line) for _, line, name, _ in parentless}
    failures: list[str] = []
    if total != 6:
        failures.append(f"counted {total} constructions, expected 6")
    if not any(name == "QLabel" for name, _ in found):
        failures.append("the parentless QLabel('just text') was not found")
    if any(name == "QWidget" for name, _ in found):
        failures.append("QWidget(loose) is parented and was reported as parentless")
    if not any(name == "Panel" for name, _ in found):
        failures.append("Panel(jobs=None) is parentless by its own signature and was not found")
    if len([1 for name, _ in found if name == "Panel"]) != 1:
        failures.append("Panel(None, loose) is parented and was reported as parentless")
    if len(unparenting) != 1:
        failures.append(f"found {len(unparenting)} un-parenting calls, expected 1")
    for failure in failures:
        print(f"SELF-TEST FAILED: {failure}", file=sys.stderr)
    if failures:
        return 1
    print(
        "SELF-TEST PASSED: a literal-only construction is parentless, a trailing widget is a "
        "parent, a product class is judged by its own signature, and setParent was seen."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--self-test", action="store_true", help="classify a known fixture, exit")
    arguments = parser.parse_args()
    if arguments.self_test:
        return self_test()

    parentless, total, unparenting = audit(SRC)
    print(f"widget constructions in {SRC}: {total}")
    print(f"without a Qt parent: {len(parentless)}\n")
    for path, line, name, source in parentless:
        print(f"  {path}:{line}  {name}\n      {source}")
    print(f"\ncalls that could hand a widget back to Python: {len(unparenting)}")
    for path, line, source in unparenting:
        print(f"  {path}:{line}\n      {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
