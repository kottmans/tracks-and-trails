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

#: The harness, for `--harness`. `T-238`'s crash is a test crash.
TESTS: Final = Path("tests")

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

#: Qt's item views, whose destructor is the one `T-238`'s worker died in. A widget that owns one —
#: directly or through another product widget — takes it down when Python collects it.
ITEM_VIEWS: Final = frozenset(
    {
        "QAbstractItemView",
        "QListView",
        "QTableView",
        "QTreeView",
        "QColumnView",
        "QListWidget",
        "QTableWidget",
        "QTreeWidget",
        "QUndoView",
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


def item_view_owners(trees: dict[Path, ast.Module], product: set[str]) -> set[str]:
    """Product widget classes that construct an item view, resolved transitively (`T238-R11`).

    **Structural, and it replaces a hand-picked list.** The first version of this reading named four
    classes by eye and missed at least two — `PresetManager` and `OptionsDialog` each own a
    `QListWidget` — which is the failure mode `ai/TESTING.md` §13 is about: a set chosen to fit the
    conclusion being drawn.

    **Transitive, because ownership is.** A class that constructs another product widget owning an
    item view owns one too, and that is how a `MainWindow` reaches a `QListView`.

    **What it cannot see is stated rather than discovered**: whether a *given* construction actually
    builds the view. `MainWindow` builds its queue only when equipped, so this answers *"can own"*
    and never *"does own at this site"*. `audit` reports the two separately for that reason.
    """
    builds: dict[str, set[str]] = {}
    for tree in trees.values():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or node.name not in product:
                continue
            made = builds.setdefault(node.name, set())
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
                    made.add(inner.func.id)

    owners = {name for name, made in builds.items() if made & ITEM_VIEWS}
    growing = True
    while growing:
        growing = False
        for name, made in builds.items():
            if name not in owners and made & owners:
                owners.add(name)
                growing = True
    return owners


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
    given = [keyword.value for keyword in call.keywords if keyword.arg == "parent"]
    if given:
        # **`parent=None` is not a parent** (`T238-R11`). This returned `True` for any `parent=`
        # keyword without looking at its value, so four real sites — a `PresetManager` and three
        # views written `parent=None` — were counted as parented. The direction of that error is
        # the dangerous one for this instrument: it hides candidates.
        return not all(_is_literal_none(value) for value in given)
    if name in product and name in signatures:
        parameters = signatures[name]
        if "parent" not in parameters:
            return False
        position = parameters.index("parent")
        if len(call.args) <= position:
            return False
        return not _is_literal_none(call.args[position])
    return bool(call.args) and not isinstance(call.args[-1], ast.Constant)


def _is_literal_none(node: ast.expr) -> bool:
    """Whether this argument is the literal `None`, which owns nothing."""
    return isinstance(node, ast.Constant) and node.value is None


def audit(
    root: Path, *, vocabulary: Path | None = None
) -> tuple[list[tuple[str, int, str, str]], int, list[tuple[str, int, str]]]:
    """Return the parentless construction sites, the total, and any un-parenting calls.

    **`vocabulary` asks a different question, and it is `T-238`'s** (`T238-R2`'s criterion 4:
    *"Product behavior versus test-harness behavior is established"*). Given a second tree, the
    widget *classes* are resolved from there and the construction *sites* are counted here — so
    pointing `root` at `tests/` and `vocabulary` at `src/` answers **where the harness builds a
    product widget without a parent**, which is the state that lets the collector destroy a Qt
    object off the GUI thread.

    **Qt's own classes are deliberately excluded in that mode.** A test constructing `QWidget()` as
    a scratch parent is ordinary and says nothing; a test constructing a *product* screen with no
    parent is the shape `T-238`'s arm B reproduced the abort with.
    """
    trees = {path: ast.parse(path.read_text()) for path in sorted(root.rglob("*.py"))}
    defining = (
        trees
        if vocabulary is None
        else {path: ast.parse(path.read_text()) for path in sorted(vocabulary.rglob("*.py"))}
    )
    qt = qt_widget_names(defining)
    product = product_widget_names(defining, qt)
    signatures = own_initialisers(defining, product)
    owners = item_view_owners(defining, product)
    every = qt | product if vocabulary is None else product

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
    return parentless, total, unparenting, owners


SELF_TEST_SOURCE: Final = """
from PySide6.QtWidgets import QLabel, QListWidget, QWidget

class Panel(QWidget):
    def __init__(self, jobs, parent=None):
        super().__init__(parent)

class Table(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = QListWidget(self)

class Screen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._table = Table(self)

def build():
    loose = QLabel("just text")          # parentless: a literal is not a parent
    titled = QLabel("text", loose)       # parented: last positional is a widget
    keyword = QLabel("text", parent=loose)
    orphan = Panel(jobs=None)            # parentless: its own signature says so
    adopted = Panel(None, loose)         # parented: positional lands on `parent`
    said_none = Panel(None, parent=None) # parentless: `parent=None` owns nothing (T238-R11)
    passed_none = Panel(None, None)      # parentless: the signature-mapped positional is None
    view_owner = Table()                 # parentless, and it owns a QListWidget
    inherited = QWidget(loose)
    loose.setParent(None)                # an un-parenting call
    return titled, keyword, orphan, adopted, said_none, passed_none, view_owner, inherited
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
        parentless, total, unparenting, _owners = audit(fixture)
    found = {(name, line) for _, line, name, _ in parentless}
    failures: list[str] = []
    if total != 11:
        failures.append(f"counted {total} constructions, expected 11")
    if not any(name == "QLabel" for name, _ in found):
        failures.append("the parentless QLabel('just text') was not found")
    if any(name == "QWidget" for name, _ in found):
        failures.append("QWidget(loose) is parented and was reported as parentless")
    if not any(name == "Panel" for name, _ in found):
        failures.append("Panel(jobs=None) is parentless by its own signature and was not found")
    # `Panel` is constructed four times and exactly three are parentless, so the `said_none` count
    # below also asserts that `Panel(None, loose)` — the parented one — stayed out.
    if len(unparenting) != 1:
        failures.append(f"found {len(unparenting)} un-parenting calls, expected 1")

    # **`parent=None` and a positional `None` are not parents** (`T238-R11`). Both arms, because
    # the two travel through different branches of `is_parented` and the keyword one is what
    # actually miscounted four sites in `tests/`.
    said_none = [line for name, line in found if name == "Panel"]
    if len(said_none) != 3:
        failures.append(
            f"found {len(said_none)} parentless Panel constructions, expected 3: the keyword "
            "`parent=None`, the positional `None`, and the one that names no parent at all"
        )

    # **Item-view ownership is transitive, and `Screen` never mentions one** (`T238-R11`). It owns
    # a `Table`, which owns a `QListWidget`; a set built by eye is how `PresetManager` and
    # `OptionsDialog` were missed.
    with tempfile.TemporaryDirectory(prefix="t289-owners-") as directory:
        fixture = Path(directory)
        (fixture / "sample.py").write_text(SELF_TEST_SOURCE)
        _p, _t, _u, owners = audit(fixture)
    for expected in ("Table", "Screen"):
        if expected not in owners:
            failures.append(f"{expected} owns an item view and was not classified as one")
    if "Panel" in owners:
        failures.append("Panel owns no item view and was classified as one")

    # **The vocabulary split, which `--harness` is** (`T-238`). Given the same fixture as both
    # trees, only the *product* class may be counted: a test constructing `QWidget()` as a scratch
    # parent is ordinary and answers nothing. Asserted because a mode that quietly matched nothing
    # would report a confident "no parentless product widgets in the harness" — the shape
    # `ai/TESTING.md` §13 is about, and the one this whole tool exists downstream of.
    with tempfile.TemporaryDirectory() as directory:
        fixture = Path(directory)
        (fixture / "sample.py").write_text(SELF_TEST_SOURCE)
        split, split_total, _unparent, _own = audit(fixture, vocabulary=fixture)
    names = {name for _path, _line, name, _source in split}
    if not names:
        failures.append("the vocabulary split found nothing at all, so --harness measures nothing")
    if any(name.startswith("Q") for name in names):
        failures.append(f"the vocabulary split counted Qt's own classes: {sorted(names)}")
    if "Panel" not in names:
        failures.append("the vocabulary split missed the parentless product widget")
    if split_total >= total:
        failures.append(
            f"the split counted {split_total} constructions against {total} unsplit; it is "
            "supposed to be narrower"
        )
    for failure in failures:
        print(f"SELF-TEST FAILED: {failure}", file=sys.stderr)
    if failures:
        return 1
    print(
        "SELF-TEST PASSED: a literal-only construction is parentless, a trailing widget is a "
        "parent, a product class is judged by its own signature, and setParent was seen."
    )
    return 0


def _report_item_views(parentless: list[tuple[str, int, str, str]], owners: set[str]) -> None:
    """Report the item-view question as its own predicate, never folded into the count above.

    **Three different things were being merged** (`T238-R11`): parentless at construction, still
    Python-owned afterwards, and able to destroy an item-view descendant. This prints only the
    third, and prints it as *"can own"* — whether a given site's widget actually builds its view is
    not decidable here, and `MainWindow` is the case that proves it: it builds a queue only when
    equipped.
    """
    among = sorted({name for _p, _l, name, _s in parentless if name in owners})
    sites = [record for record in parentless if record[2] in owners]
    print(f"\nof those, classes that CAN own an item view (transitively): {len(sites)} sites")
    print(f"  classes: {', '.join(among) or 'none'}")
    print(
        "  **`can own` is not `does own here`** — a construction that does not equip the widget "
        "builds no view. This number is an upper bound on the sites that could run "
        "`~QAbstractItemView`, not a count of the ones that would."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--self-test", action="store_true", help="classify a known fixture, exit")
    parser.add_argument(
        "--harness",
        action="store_true",
        help="scan tests/ for parentless constructions of product widget classes (T-238)",
    )
    arguments = parser.parse_args()
    if arguments.self_test:
        return self_test()

    if arguments.harness:
        parentless, total, unparenting, owners = audit(TESTS, vocabulary=SRC)
        print(f"product-widget constructions in {TESTS}: {total}")
        print(f"without a Qt parent at the call site: {len(parentless)}\n")
        for path, line, name, source in parentless:
            print(f"  {path}:{line}  {name}\n      {source}")
        _report_item_views(parentless, owners)
        print(f"\ncalls that could hand a widget back to Python: {len(unparenting)}")
        for path, line, source in unparenting:
            print(f"  {path}:{line}\n      {source}")
        return 0

    parentless, total, unparenting, owners = audit(SRC)
    print(f"widget constructions in {SRC}: {total}")
    print(f"without a Qt parent: {len(parentless)}\n")
    for path, line, name, source in parentless:
        print(f"  {path}:{line}  {name}\n      {source}")
    _report_item_views(parentless, owners)
    print(f"\ncalls that could hand a widget back to Python: {len(unparenting)}")
    for path, line, source in unparenting:
        print(f"  {path}:{line}\n      {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
