"""The seams `T-013` promises are real, read from the source rather than from behaviour.

One of the task's acceptance criteria is about what the manager may *depend on*, and it cannot
be observed by running it: a manager that imported `persistence` directly would pass every
behavioural test in `tests/integration/test_manager.py`, because those hand it a fake and never
ask where the type came from. So this reads the modules statically, the way
`tests/unit/test_layering.py` reads the layer boundaries and for the same reason — the
dependency erodes silently, and by the time anything fails it is load-bearing.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "tracks_and_trails"

#: The GUI-side modules `T-013` owns.
MODULES = ("downloader/manager.py", "downloader/result_pump.py")

#: The distribution these modules live in. Needed to resolve a relative import into the absolute
#: name a prohibition is written against.
PACKAGE = "tracks_and_trails"

#: What `ARCHITECTURE.md` §3 says the manager is *given* rather than builds, for **every** module in
#: `MODULES`. `sqlite3` is listed alongside the package because importing the engine directly is the
#: same dependency wearing a disguise.
FORBIDDEN_EVERYWHERE = (
    "tracks_and_trails.persistence",
    "sqlite3",
)

#: Prohibitions that belong to **one** module, because the decision behind them does.
#:
#: **`core.settings` is `ARC-007`, and `ARC-007` is about the manager** (`T-097`, `P2PLAN-R8`). The
#: manager receives the concurrency value and a way to be told it changed; composition and the UI
#: own the TOML file. That rule has no other gate — the layering test permits `downloader/` →
#: `core/`, so a direct settings import was measured passing both analysers.
#:
#: **It applies to `manager.py` alone.** An earlier version of this file forbade it in
#: `result_pump.py` too, on the reasoning that neither is a place a settings file should be read.
#: That may well be true, but `ARC-007` does not say it: extending an accepted decision to a module
#: it does not name is a decision, not an implementation choice, and this file is not where one gets
#: made. If the pump should be covered, `ARC-007` should say so first.
FORBIDDEN_BY_MODULE = {
    "downloader/manager.py": ("tracks_and_trails.core.settings",),
}


def forbidden_for(module: str) -> tuple[str, ...]:
    """Every prohibition that binds `module` — the shared ones plus its own."""
    return FORBIDDEN_EVERYWHERE + FORBIDDEN_BY_MODULE.get(module, ())


#: Which decision each prohibition serves, and therefore what a failure should send somebody to
#: read (`T-099`, `T097-R2`).
#:
#: **The gate was right and its diagnostic was wrong.** `T097-R1` split the manager-only settings
#: rule from the persistence rules shared by both modules, but the real-source assertion still
#: combined their offenders and always explained repository injection — so a real `core.settings`
#: import failed the correct gate while sending the reader to `T-013`'s rule about a repository it
#: had not imported. A diagnostic that names the wrong decision costs more than none: it is
#: believed.
#:
#: Keyed by prohibition rather than by module, because the *rule* is what was violated. Matching is
#: by prefix, exactly as `offenders` matches.
WHY_FORBIDDEN = {
    "tracks_and_trails.persistence": (
        "The repository is injected as a protocol, not imported: see ARCHITECTURE.md §3 and "
        "DownloadManager's docstring (T-013)."
    ),
    "sqlite3": (
        "Importing the engine directly is the repository dependency wearing a disguise: see "
        "ARCHITECTURE.md §3 and DownloadManager's docstring (T-013)."
    ),
    "tracks_and_trails.core.settings": (
        "ARC-007 gives the manager a concurrency value and a way to be told it changed; "
        "composition and the UI own settings.toml. Inject the value, do not read the file (T-097)."
    ),
}


def explain(offender: str) -> str:
    """Why `offender` is forbidden, in the words of the decision that forbids it.

    Falls back to naming the offender rather than guessing. A prohibition added to
    `FORBIDDEN_EVERYWHERE` or `FORBIDDEN_BY_MODULE` without a matching explanation should read as
    an unexplained rule, not as one of the rules that happens to be listed first — that
    substitution is the defect `T-099` exists to fix.
    """
    for forbidden, reason in WHY_FORBIDDEN.items():
        if offender == forbidden or offender.startswith(f"{forbidden}."):
            return reason
    return f"{offender} is forbidden here, and no rule in WHY_FORBIDDEN explains why."


def _absolute(module: str, node: ast.ImportFrom) -> str:
    """The absolute module name `node` imports *from*, resolving `.` and `..` against `module`.

    **Relative imports were unchecked entirely until `T-097`'s correction**, and that is the hole
    this function exists to close. The analyser skipped any `ImportFrom` with `node.level != 0`, so
    `from ..core import settings` — and `from .. import persistence`, the original prohibition —
    both passed every case in this file. Measured surviving all 23 before the fix.

    `module` is a repository-relative path like `downloader/manager.py`. Its package is
    `tracks_and_trails.downloader`; one leading dot means that package, two means its parent, and so
    on outward. A level that walks past the distribution root yields `""`, which cannot prefix-match
    any prohibition — the honest answer for an import that would not resolve at run time either.
    """
    if node.level == 0:
        return node.module or ""
    parts = [PACKAGE, *Path(module).parent.parts]
    # One dot is the containing package; each extra dot climbs one level.
    climbed = parts[: len(parts) - (node.level - 1)] if node.level > 1 else parts
    base = ".".join(climbed)
    if not base:
        return ""
    return f"{base}.{node.module}" if node.module else base


def imported_modules(source: str, module: str = "downloader/manager.py") -> set[str]:
    """Every module named by an `import` anywhere in `source`, including inside functions.

    A lazy import is still an import: deferring `from ... import JobRepository` into a method
    would make the dependency invisible at the top of the file and no less real.

    `module` is the repository-relative path `source` stands in for, and it is **not** cosmetic:
    relative imports can only be resolved against it. It defaults to `downloader/manager.py` because
    that is what every synthetic case in this file is pretending to be.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(source, filename=module)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _absolute(module, node)
            if not base:
                continue
            names.add(base)
            # **`from package import submodule` names a module too** (`T-097`). Recording only the
            # base missed it: `from tracks_and_trails.core import settings` looked like an import of
            # `tracks_and_trails.core`, which is permitted, while binding the settings module
            # itself. The same hole let `from tracks_and_trails import persistence` through —
            # the original prohibition, unreachable by its own most natural spelling.
            #
            # `alias.name`, never `alias.asname`: the module path is what was imported, not what it
            # was called locally. `from x import y as z` is still an import of `x.y`.
            names.update(f"{base}.{alias.name}" for alias in node.names)
    return names


def offenders(source: str, module: str = "downloader/manager.py") -> set[str]:
    """The forbidden dependencies `source` takes on, submodules included.

    Which prohibitions apply depends on `module`: `core.settings` binds the manager only, because
    `ARC-007` is about the manager only.
    """
    rules = forbidden_for(module)
    return {
        name
        for name in imported_modules(source, module)
        if any(name == forbidden or name.startswith(f"{forbidden}.") for forbidden in rules)
    }


@pytest.mark.parametrize("module", MODULES)
def test_the_manager_never_imports_persistence(module: str) -> None:
    """The injected boundary cannot quietly collapse into a direct dependency (`T-013`).

    `ARCHITECTURE.md` §3 gives `DownloadManager` a repository; the manager takes a protocol and
    `app.py` supplies the concrete one at composition time (`T-036`). A single
    `from ...persistence import JobRepository` — added for a type annotation, say — makes the
    protocol decorative and the unit tests a fiction.
    """
    path = SRC / module
    found = offenders(path.read_text(encoding="utf-8"), module)
    # **One line per violated rule** (`T-099`). Combining them under a single explanation is what
    # sent a real settings import to the repository-injection rule; `explain` keys the reason to the
    # prohibition that actually matched, and the set keeps it to one line per distinct rule.
    reasons = sorted({explain(offender) for offender in found})
    assert not found, "{} imports {}.\n{}".format(module, sorted(found), "\n".join(reasons))


@pytest.mark.parametrize(
    "source",
    [
        "import sqlite3",
        "from tracks_and_trails.persistence.repositories import JobRepository",
        "from tracks_and_trails.persistence import db",
        "import tracks_and_trails.persistence.db",
        "def build():\n    from tracks_and_trails.persistence import db\n",
        # `T-097` / `ARC-007`: every spelling of the settings dependency.
        "from tracks_and_trails.core import settings",
        "from tracks_and_trails.core.settings import concurrency_limit",
        "import tracks_and_trails.core.settings",
        "from tracks_and_trails.core import settings as s",
        "def read():\n    from tracks_and_trails.core import settings\n",
        # The hole `T-097` found while adding the above: the persistence prohibition's own most
        # natural spelling was unreachable.
        "from tracks_and_trails import persistence",
        # **Relative imports, unchecked until `T097-R1`.** The analyser skipped every `ImportFrom`
        # with a non-zero level, so each of these survived all 23 cases in this file — including the
        # persistence prohibition's own relative spellings, which predate `T-097` entirely.
        "from ..core import settings",
        "from ..core.settings import concurrency_limit",
        "from ..core import settings as s",
        "from .. import persistence",
        "from ..persistence import db",
        "from ..persistence.repositories import JobRepository",
        "def read():\n    from ..core import settings\n",
    ],
)
def test_the_check_above_can_actually_fail(source: str) -> None:
    """`ai/TESTING.md` §13: a guard nobody has watched fail is not evidence.

    Every form the dependency could take is put through the real analyser, so narrowing it —
    dropping `sqlite3`, matching only exact module names, ignoring imports inside functions —
    fails here instead of passing silently against a tree that happens to be clean.
    """
    assert offenders(source), f"{source!r} would not have been caught"


@pytest.mark.parametrize(
    "source",
    [
        "from tracks_and_trails.core.models import Job",
        "import multiprocessing",
        # `ARC-007` forbids the settings module, not `core/` (`T-097`). Each of these is something
        # the real manager does today, and a prohibition that caught them would be deleted by
        # whoever it blocked — taking the settings gate with it.
        "from tracks_and_trails.core import logging as app_logging",
        "from tracks_and_trails.core.errors import ErrorKind",
        "from tracks_and_trails.core.job_state import JobStatus, is_terminal",
        "from tracks_and_trails.core import models",
        "import tracks_and_trails.core.models",
        # Adjacent names that merely start the same way must not be swept up.
        "from tracks_and_trails.core.settings_helpers import thing",
        "import tracks_and_trails.core.settingsish",
        # Relative imports the manager legitimately makes. Resolving them (`T097-R1`) must not turn
        # every sibling import into a violation.
        "from . import protocol",
        "from .protocol import Succeeded",
        "from ..core.models import Job",
        "from ..core import logging as app_logging",
        "from ..core.job_state import JobStatus",
    ],
)
def test_a_legitimate_import_is_not_reported(source: str) -> None:
    """False positives get a check deleted by whoever they block, taking the real one with them."""
    assert not offenders(source), f"{source!r} was reported and should not be"


def test_the_modules_under_test_exist() -> None:
    """Guards against every check above passing because a path was renamed."""
    for module in MODULES:
        assert (SRC / module).is_file(), f"{module} does not exist; the checks above are vacuous"


# --- ARC-007's scope is the manager, and only the manager (`T097-R1`) ----------------------


SETTINGS_FORMS = (
    "from tracks_and_trails.core import settings",
    "from tracks_and_trails.core.settings import concurrency_limit",
    "import tracks_and_trails.core.settings",
    "from ..core import settings",
)


@pytest.mark.parametrize("source", SETTINGS_FORMS)
def test_the_settings_prohibition_binds_the_manager(source: str) -> None:
    """`ARC-007` names `downloader/manager.py`: it receives the value, it does not read the file."""
    assert offenders(source, "downloader/manager.py"), f"{source!r} escaped the manager's rule"


@pytest.mark.parametrize("source", SETTINGS_FORMS)
def test_the_settings_prohibition_does_not_bind_the_result_pump(source: str) -> None:
    """`P2PLAN-R8`/`T097-R1`: extending an accepted decision is a decision, not a lint choice.

    An earlier version forbade `core.settings` in `result_pump.py` too, reasoning that neither
    module should read a settings file. That may be right, but `ARC-007` does not say it, and this
    file is not where it gets decided. **If the pump should be covered, `ARC-007` should say so
    first** — and then this test is what changes, deliberately.
    """
    assert not offenders(source, "downloader/result_pump.py"), (
        f"{source!r} was reported for result_pump.py, which ARC-007 does not name"
    )


@pytest.mark.parametrize("module", MODULES)
@pytest.mark.parametrize(
    "source",
    [
        "from tracks_and_trails.persistence import db",
        "from tracks_and_trails import persistence",
        "from .. import persistence",
        "import sqlite3",
    ],
)
def test_the_persistence_prohibition_binds_every_module(source: str, module: str) -> None:
    """`T-013`'s rule is not module-specific and must not have become so when the rules split."""
    assert offenders(source, module), f"{source!r} escaped {module}"


def test_every_module_the_rules_name_is_a_module_under_test() -> None:
    """A per-module table can name a file that no longer exists, and then it gates nothing."""
    for module in FORBIDDEN_BY_MODULE:
        assert module in MODULES, f"{module} has rules but is not checked"
        assert (SRC / module).is_file(), f"{module} has rules but does not exist"


# --- T-099 / T097-R2: the failure names the rule that was broken ---------------------------


def test_a_real_settings_import_fails_with_the_arc_007_diagnostic() -> None:
    """`T-099`: the gate was already right; the reason it gave was not.

    Driven through `explain` against a real offender rather than by editing `manager.py` on disk,
    because the assertion under test is a string and the file is under review. What is proven is
    the mapping the assertion uses.
    """
    reason = explain("tracks_and_trails.core.settings")

    assert "ARC-007" in reason, f"a settings import is explained as: {reason}"
    assert "settings.toml" in reason
    assert "repository" not in reason.lower(), (
        "a settings import is still explained by the repository-injection rule, which is exactly "
        "T097-R2: the correct gate failing with the wrong reason"
    )


def test_the_real_gate_uses_the_arc_007_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the failing assertion, not only the helper that supplies its text."""
    source_root = tmp_path / "tracks_and_trails"
    module = source_root / "downloader" / "manager.py"
    module.parent.mkdir(parents=True)
    module.write_text("from tracks_and_trails.core import settings\n", encoding="utf-8")
    monkeypatch.setattr("tests.unit.test_manager_boundaries.SRC", source_root)

    with pytest.raises(AssertionError) as raised:
        test_the_manager_never_imports_persistence("downloader/manager.py")

    diagnostic = str(raised.value)
    assert "ARC-007" in diagnostic
    assert "settings.toml" in diagnostic
    assert "repository is injected" not in diagnostic.lower()


def test_a_real_persistence_import_fails_with_the_t_013_diagnostic() -> None:
    """The other half, and it must not drift into naming ARC-007 instead."""
    for offender in (
        "tracks_and_trails.persistence",
        "tracks_and_trails.persistence.repositories",
        "sqlite3",
    ):
        reason = explain(offender)
        assert "ARCHITECTURE.md §3" in reason, f"{offender} is explained as: {reason}"
        assert "ARC-007" not in reason, f"{offender} is explained by the settings rule"


def test_every_prohibition_has_an_explanation() -> None:
    """A rule added without a reason must read as unexplained, not inherit the first one listed.

    This is the invariant that stops `T-099` from decaying: `explain` falls back to saying so, and
    this asserts no live prohibition is currently in that state.
    """
    live = set(FORBIDDEN_EVERYWHERE)
    for extra in FORBIDDEN_BY_MODULE.values():
        live.update(extra)

    unexplained = [rule for rule in sorted(live) if "no rule in WHY_FORBIDDEN" in explain(rule)]

    assert not unexplained, (
        f"{unexplained} are enforced with no explanation. Add one to WHY_FORBIDDEN naming the "
        "decision, or a future violation will fail with a message that names the wrong rule"
    )


def test_two_rules_broken_at_once_report_both() -> None:
    """A module violating both prohibitions must be told about both, not the first one found."""
    source = (
        "from tracks_and_trails.core import settings\n"
        "from tracks_and_trails.persistence import db\n"
    )
    found = offenders(source)
    reasons = sorted({explain(offender) for offender in found})

    assert len(reasons) == 2, f"two distinct rules were broken and {len(reasons)} were explained"
    assert any("ARC-007" in reason for reason in reasons)
    assert any("ARCHITECTURE.md §3" in reason for reason in reasons)
