"""yt-dlp and ffmpeg resolution (`T-035`).

Two things are under test, and the second is the one that erodes quietly.

**Behavior**: the `OPS-002` resolution order, and an ffmpeg report that names what stops
working (`REQ-024`).

**The ownership boundary**: this module *locates*, `worker.py` *imports*. `ARCHITECTURE.md` §6
permits `import yt_dlp` in two modules and this is not one of them, so `environment.py` cannot
report a version or a usability verdict — both need the import. That boundary is asserted here
rather than left to the layering test alone, because the tempting way to erode it is to add a
helpful `version()` that reaches for `importlib`, which the layering test's `ast` analysis would
not necessarily see as an `import yt_dlp`.
"""

import ast
import importlib.metadata
import importlib.util
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from tracks_and_trails.core.paths import APP_SLUG
from tracks_and_trails.downloader import environment
from tracks_and_trails.downloader.environment import (
    FFMPEG_DEPENDENT_FEATURES,
    FfmpegReport,
    describe_candidates,
    find_ffmpeg,
    user_ytdlp_directory,
    ytdlp_candidates,
)

# --- resolution order (OPS-002, ARCHITECTURE.md §6) -----------------------------------------


def test_with_no_user_copy_the_candidate_list_is_the_baseline_alone(tmp_path: Path) -> None:
    """`T035-R1`. The acceptance criterion, asserted against the tuple itself.

    The earlier version filtered to "present" candidates and asserted on the projection, which
    silently weakened the criterion from *the list contains the baseline alone* to *the baseline
    is the only present entry* — and passed against an implementation that always returned two.
    A caller walking the tuple would have had to know to filter.
    """
    candidates = ytdlp_candidates(tmp_path / "absent")
    assert len(candidates) == 1
    assert candidates[0].path is None
    assert "baseline" in candidates[0].source


def test_a_user_copy_is_ordered_ahead_of_the_baseline(tmp_path: Path) -> None:
    """The whole point of `OPS-002`: a user fixes a broken site without waiting for a release."""
    user_copy = tmp_path / "ytdlp"
    user_copy.mkdir()
    candidates = ytdlp_candidates(user_copy)

    assert len(candidates) == 2
    assert candidates[0].path == user_copy
    assert candidates[1].path is None


@pytest.mark.parametrize("layout", ["empty", "no yt_dlp package", "unexpected wheel layout"])
def test_a_user_directory_is_listed_even_when_it_looks_unusable(
    tmp_path: Path, layout: str
) -> None:
    """An acceptance criterion, and the one most likely to be "helpfully" broken later.

    Deciding a candidate is unusable requires importing it, which is `worker.py`'s job. A
    `yt_dlp/`-directory check here would be this module forming the verdict it may not form —
    and would be wrong for any wheel layout this code has not anticipated.
    """
    user_copy = tmp_path / "ytdlp"
    user_copy.mkdir()
    if layout == "no yt_dlp package":
        (user_copy / "something_else").mkdir()
    elif layout == "unexpected wheel layout":
        (user_copy / "yt_dlp-2026.7.4.dist-info").mkdir()

    candidates = ytdlp_candidates(user_copy)
    assert len(candidates) == 2
    assert candidates[0].path == user_copy


def test_a_file_where_the_user_directory_should_be_is_not_present(tmp_path: Path) -> None:
    """`is_dir()`, not `exists()`: a stray file cannot be prepended to `sys.path` usefully."""
    stray = tmp_path / "ytdlp"
    stray.write_text("not a directory", encoding="utf-8")
    assert ytdlp_candidates(stray) == (ytdlp_candidates(tmp_path / "absent"))


def test_the_default_user_directory_is_not_doubled() -> None:
    """platformdirs inserts an author segment on Windows without `appauthor=False`.

    That produces `tracksandtrails/tracksandtrails/ytdlp`, matching none of `ARCHITECTURE.md`
    §5's paths — invisible on Linux, wrong on Windows. The trap `T-007` already hit once.
    """
    path = user_ytdlp_directory()
    assert path.name == "ytdlp"
    assert path.parent.name == APP_SLUG
    assert path.parent.parent.name != APP_SLUG


# --- the ownership boundary (ARCHITECTURE.md §6) ---------------------------------------------


#: The public API this module is reviewed to have, transcribed by hand.
#:
#: Not derived from the module (`T010-R1`'s recurring lesson): asking production what it exports
#: and then checking that against itself proves nothing.
REVIEWED_PUBLIC_API = frozenset(
    {
        "BASELINE_YTDLP_VERSION",
        "FFMPEG_DEPENDENT_FEATURES",
        # `T-199`. **Transcribed deliberately, and it is a locate-side name.** The guard below
        # exists to stop this module answering *"what version?"* or *"does it work?"*, which need
        # an import and belong to `worker.py`. An enumeration of what ffmpeg performs answers
        # neither: it is the same fact `FFMPEG_DEPENDENT_FEATURES` already exports, in a form the
        # UI can key on so the report and the offer cannot drift.
        "FfmpegFeature",
        "FfmpegReport",
        "YtdlpCandidate",
        # `T-319`. **A locate-side name, which is why it is admitted here.** It answers *where a
        # frozen build keeps the ffmpeg it shipped with* — the same question `find_ffmpeg` asks of
        # `PATH`, on a different shelf. It imports nothing, executes nothing, and says nothing
        # about versions or whether the binary works; `OPS-001` bundles ffmpeg on Windows and this
        # is how the artifact's own copy is found before a user's `PATH`.
        "bundled_ffmpeg",
        "describe_candidates",
        "find_ffmpeg",
        "normalise_version",
        "user_ytdlp_directory",
        "ytdlp_candidates",
    }
)


#: Nodes that open a new scope. An `import` inside one binds locally and never becomes a module
#: attribute, so the walk yields the node and does not descend into it.
_NESTED_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def _module_scope_nodes(node: ast.AST) -> Iterator[ast.AST]:
    """Every node evaluated in the module's own scope, however deeply nested in control flow.

    Descends through `if`/`try`/`for`/`while`/`match` so a conditional import is found, and stops
    at a nested scope. **Used only to locate `import` statements** — see `defined_public_names`
    for why this file no longer tries to detect *bindings* by parsing.

    Stopping at the whole `def`/`class`/`lambda` is exact for that job: an `import` is a
    statement, so it cannot hide in a decorator, default argument, annotation or base-class
    expression. It was *not* exact for binding detection, which is what `T044-R1` kept proving.
    """
    for child in ast.iter_child_nodes(node):
        yield child
        if not isinstance(child, _NESTED_SCOPES):
            yield from _module_scope_nodes(child)


def _imported_names(tree: ast.Module) -> set[str]:
    """Names the module binds by importing them, which are not part of its own public API.

    `import importlib.metadata` binds `importlib`, not `importlib.metadata` — hence the split on
    the first dot when there is no `as` clause.
    """
    names: set[str] = set()
    for node in _module_scope_nodes(tree):
        if isinstance(node, ast.Import):
            names.update(a.asname or a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(a.asname or a.name for a in node.names)
    return names


def defined_public_names(module: ModuleType) -> set[str]:
    """Public attributes of `module` that no `import` statement in its source accounts for.

    **Read the promise literally; it is deliberately small** (`T044-R1`, sixth round, third
    maintainer decision). Every earlier version of this docstring claimed more than it delivered,
    and the reviewer disproved each claim in turn. What follows is only what is demonstrated by
    the tests below.

    **Guaranteed.** On the interpreter, platform and configuration the suite actually runs under,
    a public attribute of the module that was not bound by an `import` statement appears here.
    `vars()` is the interpreter's own namespace, so this holds for any binding syntax — a
    conditional definition, destructuring, a `match` capture, a walrus in a default argument —
    including syntax that does not exist yet. That is the property five rounds of parsing failed
    to achieve, and it is achieved by not parsing for bindings at all.

    **Not guaranteed, each pinned by a test rather than left to memory:**

    - *Anything behind a guard that is false when the suite runs.* Not merely OS guards —
      architecture, dependency presence, feature availability, environment state. A runtime gate
      cannot see a binding that never happened, and no CI matrix changes that in general. An
      earlier version of this docstring claimed the `windows-latest` job covered this; it covers
      only guards that are true on Windows and false on Linux, which is one narrow case.
      Pinned by `test_an_export_behind_a_guard_that_is_false_here_is_invisible`.
    - *A name imported and then rebound.* `try: from x import Y / except ImportError: Y = ...`
      leaves a genuine public constant, while the parse sees `Y` as an import and subtracts it.
      Pinned by `test_a_fallback_after_a_failed_import_is_a_known_blind_spot`.
    - *Dynamic rebinding of an imported name*, `globals()["Path"] = ...`.
      Pinned by `test_a_dynamically_rebound_import_alias_is_a_known_blind_spot`.

    **What it is for.** Catching the *accidental* erosion of the locate/import split — someone
    adding a helpful `get_ytdlp_version()` to a module that `ARCHITECTURE.md` §6 says may not
    answer that question. It is not a security boundary and does not defend against an author
    working to hide an export. `T-047` carries the gaps above; closing them is not a condition of
    this gate being useful for what it does catch.
    """
    tree = ast.parse(Path(module.__file__ or "").read_text(encoding="utf-8"))
    public = set(vars(module)) - _imported_names(tree)
    return {name for name in public if not name.startswith("_")}


def test_the_module_exposes_no_version_and_no_usability_verdict() -> None:
    """An acceptance criterion: the split must not erode back into this module by accident.

    Both a version and a "does it work" answer require importing yt-dlp, which §6 permits only
    in `worker.py` and `ytdlp_adapter.py`. A helper named `version()` here would be a layering
    violation wearing a friendly name.

    **An allowlist, not a denylist** (`T035-R3`). The earlier version named six forbidden
    strings, so an ordinary `get_ytdlp_version()` export passed all 20 tests while violating
    exactly the split this test claims to protect. Guessing the names a future author will
    choose is unwinnable; pinning the reviewed API means *any* new export has to be justified,
    which is the conversation worth forcing.
    """
    added = defined_public_names(environment) - REVIEWED_PUBLIC_API
    assert not added, (
        f"{sorted(added)} is not in this module's reviewed public API. Adding an export here is "
        "how the locate/import split erodes: anything answering 'what version?' or 'does it "
        "work?' needs an import and belongs to worker.py (ARCHITECTURE.md §6)."
    )
    removed = REVIEWED_PUBLIC_API - defined_public_names(environment)
    assert not removed, f"{sorted(removed)} disappeared from the module's public API"

    candidate = ytdlp_candidates()[0]
    assert not hasattr(candidate, "version")
    assert not hasattr(candidate, "usable")


def _module_from_source(tmp_path: Path, name: str, source: str) -> ModuleType:
    """Load `source` as a real module so the runtime gate sees a genuine namespace."""
    path = tmp_path / f"{name}.py"
    path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: Export shapes the gate must catch. Each binds `SMUGGLED` at module scope by a different route.
#:
#: The first two are `T044-R1`'s survivors: a definition under module-level control flow, and one
#: made by destructuring. Both were runtime-present and left the ownership test green.
SMUGGLING_ROUTES = [
    pytest.param("if os.name:\n    SMUGGLED = 'unreviewed'\n", id="conditional"),
    pytest.param("SMUGGLED, OTHER = ('unreviewed', True)\n", id="destructuring"),
    pytest.param("SMUGGLED, *REST = ('unreviewed', 1, 2)\n", id="star-unpacking"),
    pytest.param("try:\n    SMUGGLED = 'unreviewed'\nexcept OSError:\n    pass\n", id="try-block"),
    pytest.param("for SMUGGLED in ('unreviewed',):\n    pass\n", id="for-target"),
    pytest.param(
        "import contextlib\nwith contextlib.suppress() as SMUGGLED:\n    pass\n", id="with-as"
    ),
    pytest.param("if (SMUGGLED := 'unreviewed'):\n    pass\n", id="walrus"),
    pytest.param("type SMUGGLED = int\n", id="type-alias"),
    pytest.param("SMUGGLED: str = 'unreviewed'\n", id="annotated"),
    pytest.param("def SMUGGLED() -> None:\n    pass\n", id="function"),
    pytest.param("class SMUGGLED:\n    pass\n", id="class"),
    # No ordinary assignment statement binds this one; runtime namespace inspection still sees it.
    pytest.param("globals()['SMUGGLED'] = 'unreviewed'\n", id="globals-assignment"),
    pytest.param("match 'x':\n    case str() as SMUGGLED:\n        pass\n", id="match-as"),
    pytest.param("match ['x']:\n    case [*SMUGGLED]:\n        pass\n", id="match-star"),
    pytest.param("match {'k': 1}:\n    case {**SMUGGLED}:\n        pass\n", id="match-mapping"),
]


@pytest.mark.parametrize("source", SMUGGLING_ROUTES)
def test_every_export_shape_reaches_the_reviewed_api_gate(tmp_path: Path, source: str) -> None:
    """`T044-R1`. The gate must not depend on guessing how an export was written.

    The previous version walked `tree.body` directly and read only simple-`Name` assignment
    targets, so `if os.name: YTDLP_VERSION = ...` and `YTDLP_VERSION, YTDLP_USABLE = ...` both
    passed it while being ordinary public exports at runtime. That is the third time this gate
    was defeated by an unenumerated shape, which is why it no longer relies on enumeration alone.
    """
    module = _module_from_source(tmp_path, f"shape_{abs(hash(source))}", f"import os\n{source}")
    assert "SMUGGLED" in defined_public_names(module)


def test_an_export_behind_a_guard_that_is_false_here_is_invisible(tmp_path: Path) -> None:
    """**A known limit, pinned rather than papered over** (`T044-R1`, sixth round).

    A runtime gate cannot see a binding that never happened. An earlier version of this file
    claimed the `windows-latest` CI job covered this; it does not. That job covers guards which
    are true on Windows and false on Linux — one narrow case. A guard on architecture, on a
    dependency being installed, on a feature probe, or on any environment state is false on both
    runners, and this probe's `nonesuch` platform is false on both too.

    So the honest statement is the one asserted here: behind a false guard, the gate sees
    nothing. `T-047` carries whether that is worth closing.
    """
    module = _module_from_source(
        tmp_path,
        "guarded_false",
        "import sys\nif sys.platform == 'nonesuch':\n    HIDDEN = 'unreviewed'\n",
    )
    assert not hasattr(module, "HIDDEN"), "the guard must not have run on this host"
    assert "HIDDEN" not in defined_public_names(module), (
        "invisible by construction. If this now fails the gate inspects source again, and the "
        "promise in defined_public_names plus docs/project/TESTING.md both need revisiting."
    )


def test_a_conditional_export_is_caught_once_its_guard_is_true(tmp_path: Path) -> None:
    """The other side: the gate does not care *why* a name was bound, only that it was.

    This is what makes the guarantee syntax-independent. It is not a claim about any particular
    CI runner — it is the general property that an executed binding is always seen.
    """
    module = _module_from_source(
        tmp_path,
        "guarded_true",
        "import sys\nif sys.platform == sys.platform:\n    REVEALED = 'unreviewed'\n",
    )
    assert "REVEALED" in defined_public_names(module)


def test_a_fallback_after_a_failed_import_is_a_known_blind_spot(tmp_path: Path) -> None:
    """**Known limit, pinned** (`T044-R1`, sixth round). An optional dependency's usual shape.

    `try: from x import Y / except ImportError: Y = default` leaves `Y` as a genuine public
    constant of this module, but the parse sees an `ImportFrom` binding `Y` and subtracts it. The
    import provenance is real; it just did not happen this time.

    Closing it means either not subtracting a name the source also assigns — which is
    re-enumerating assignment syntax, the thing that failed five times — or comparing each
    attribute's value against what the import would have produced, which a dynamic module
    defeats anyway. The maintainer chose to state the limit instead (`T-047`).
    """
    module = _module_from_source(
        tmp_path,
        "import_fallback",
        "try:\n    from nonexistent_module import YTDLP_VERSION\n"
        "except ImportError:\n    YTDLP_VERSION = 'unreviewed'\n",
    )
    assert module.YTDLP_VERSION == "unreviewed", "the fallback must have bound the name"
    assert "YTDLP_VERSION" not in defined_public_names(module), (
        "if this now fails the blind spot is closed — delete this test and the caveat with it"
    )


def test_a_dynamically_rebound_import_alias_is_a_known_blind_spot(tmp_path: Path) -> None:
    """**Declared out of scope, pinned rather than fixed** (`T044-R1`, `AGENTS.md` §9).

    Overwriting a name that entered the namespace as an import defeats the gate: runtime
    inspection sees the value, but the source parse records the name as imported and subtracts
    it. Closing this needs value-identity heuristics that a sufficiently dynamic module defeats
    anyway.

    The maintainer authorized declaring this out of the gate's supported binding model rather
    than chasing it, because the gate defends against accidental erosion of the locate/import
    split, not against an author working to hide an export. This pins the limit so it cannot
    change unnoticed: if a future version *does* catch it, this test fails and should be deleted
    along with the caveat in `defined_public_names`.
    """
    module = _module_from_source(
        tmp_path,
        "rebound_alias",
        "from pathlib import Path\nglobals()['Path'] = 'unreviewed'\n",
    )
    assert module.Path == "unreviewed", "the overwrite must have taken effect"
    assert "Path" not in defined_public_names(module), (
        "if this now fails the blind spot is closed — delete this test and the caveat with it"
    )


@pytest.mark.parametrize(
    ("name", "source"),
    [
        pytest.param("Path", "from pathlib import Path\n", id="from-import"),
        pytest.param("importlib", "import importlib.metadata\n", id="dotted-import"),
        pytest.param("alias", "import os as alias\n", id="aliased-import"),
        pytest.param("_PRIVATE", "_PRIVATE = 1\n", id="private-name"),
        pytest.param("LOCAL", "def f() -> None:\n    LOCAL = 1\n", id="function-local"),
        pytest.param("ATTR", "class C:\n    ATTR = 1\n", id="class-attribute"),
        # `T044-R1`, second round: these three were reported as module exports because the walk
        # descended into function bodies, and because an `except` alias is deleted on exit.
        pytest.param(
            "WALRUS", "def f() -> None:\n    if (WALRUS := 1):\n        pass\n", id="local-walrus"
        ),
        pytest.param(
            "EXC",
            "def f() -> None:\n    try:\n        pass\n    except OSError as EXC:\n        pass\n",
            id="local-except-alias",
        ),
        pytest.param(
            "EXC",
            "try:\n    pass\nexcept OSError as EXC:\n    pass\n",
            id="module-except-alias-is-deleted-on-exit",
        ),
        pytest.param("LAMBDA_LOCAL", "f = lambda: (LAMBDA_LOCAL := 1)\n", id="lambda-local-walrus"),
    ],
)
def test_the_gate_reports_neither_imports_nor_names_outside_module_scope(
    tmp_path: Path, name: str, source: str
) -> None:
    """The other direction: over-reporting would make the gate noise nobody reads.

    An import is not this module's API, a private name is not public, a binding inside a `def`,
    `lambda` or `class` body never becomes a module attribute, and Python deletes an `except ...
    as` target when the handler exits so it is never one either.
    """
    module_name = f"excluded_{name.strip('_')}_{abs(hash(source))}"
    assert name not in defined_public_names(_module_from_source(tmp_path, module_name, source))


def imported_roots(module: object) -> set[str]:
    """Top-level package names this module actually imports, by parsing it.

    Parsed rather than substring-matched: the module's docstring discusses `yt_dlp` at length
    precisely to explain why it does not import it, and a naive `"yt_dlp" not in source` check
    fails on the explanation. That was the first version of this test.
    """
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))  # type: ignore[attr-defined]
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_the_module_never_imports_yt_dlp() -> None:
    """An acceptance criterion. `ARCHITECTURE.md` §6 permits the import in two modules only."""
    assert "yt_dlp" not in imported_roots(environment)


def test_the_module_cannot_reach_yt_dlp_dynamically() -> None:
    """Stronger than the layering test's static analysis, and the reason this test exists.

    `test_layering.py` looks for an `import yt_dlp` statement. `importlib.import_module("yt_dlp")`
    is not one, so it would pass that guard while violating §6 exactly as much. Blocking the
    tool rather than the spelling is what makes the boundary hold.
    """
    assert "importlib" not in imported_roots(environment)
    source = Path(environment.__file__).read_text(encoding="utf-8")
    assert "__import__" not in source


def test_the_module_imports_no_qt() -> None:
    """Resolution runs in the worker, which must stay Qt-free (`ARC-002`)."""
    roots = imported_roots(environment)
    assert "PySide6" not in roots
    assert "shiboken6" not in roots


def make_fake_ffmpeg(directory: Path, name: str = "ffmpeg", executable: bool = True) -> Path:
    """Create a fake ffmpeg for the host platform, executable unless asked otherwise.

    Windows resolves executables through `PATHEXT`, so a file simply named `ffmpeg` is not
    found by `shutil.which` there — the Windows job failed on exactly that while Linux passed.
    The production code was right; the fixture assumed POSIX semantics.

    `executable` exists because the positive override fixture used to create a mode-0644 file
    and assert it was available, enshrining the bug `T035-R2` found.
    """
    directory.mkdir(parents=True, exist_ok=True)
    binary = directory / (f"{name}.exe" if sys.platform == "win32" else name)
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755 if executable else 0o644)
    return binary


# --- ffmpeg detection (REQ-024, OPS-001) -----------------------------------------------------


def test_ffmpeg_found_on_path_reports_available(tmp_path: Path) -> None:
    fake = make_fake_ffmpeg(tmp_path)

    report = find_ffmpeg(search_path=str(tmp_path))
    assert report.available
    assert report.path == fake
    assert report.unavailable_features == ()


def test_ffmpeg_absent_names_every_feature_that_stops_working(tmp_path: Path) -> None:
    """`REQ-024`: report *which* features are unavailable, not merely that some are.

    A user told "some features are unavailable" cannot decide whether they care.
    """
    report = find_ffmpeg(search_path=str(tmp_path / "empty"))
    assert not report.available
    assert report.unavailable_features == FFMPEG_DEPENDENT_FEATURES
    assert "merging" in report.summary()
    assert "audio" in report.summary()


def test_an_explicit_override_is_honoured_first(tmp_path: Path) -> None:
    """`OPS-001` allows an override on both platforms."""
    override = make_fake_ffmpeg(tmp_path / "custom", name="custom-ffmpeg")
    on_path = make_fake_ffmpeg(tmp_path / "onpath").parent

    report = find_ffmpeg(override=override, search_path=str(on_path))
    assert report.path == override
    assert "override" in report.source


def test_a_missing_override_is_reported_not_silently_ignored(tmp_path: Path) -> None:
    """Falling back to `PATH` would mean the user's explicit setting had no effect, silently.

    `ARCHITECTURE.md` §6's rule for yt-dlp — never silently ignore an override — is the same
    principle, and a user who set a path deserves to be told it was wrong.
    """
    on_path = make_fake_ffmpeg(tmp_path / "onpath").parent

    report = find_ffmpeg(override=tmp_path / "nope", search_path=str(on_path))
    assert not report.available
    assert "override" in report.source


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX execute bits")
def test_a_non_executable_override_is_rejected(tmp_path: Path) -> None:
    """`T035-R2`. Presence is not capability.

    A mode-0644 regular file was reported available, and the summary claimed every
    post-processing feature worked when nothing could run. The `PATH` branch already got this
    right through `shutil.which`; the override branch checked only `is_file()`.
    """
    override = make_fake_ffmpeg(tmp_path / "custom", name="ffmpeg", executable=False)
    report = find_ffmpeg(override=override)

    assert not report.available
    assert report.unavailable_features == FFMPEG_DEPENDENT_FEATURES
    assert "merging" in report.summary()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX execute bits")
def test_a_non_executable_binary_on_path_is_not_found(tmp_path: Path) -> None:
    """The two branches must agree; `shutil.which` already enforces this one."""
    make_fake_ffmpeg(tmp_path / "onpath", executable=False)
    assert not find_ffmpeg(search_path=str(tmp_path / "onpath")).available


def test_a_directory_named_ffmpeg_is_not_mistaken_for_the_binary(tmp_path: Path) -> None:
    override = tmp_path / "ffmpeg"
    override.mkdir()
    assert not find_ffmpeg(override=override).available


def test_detection_executes_nothing(tmp_path: Path) -> None:
    """`ARCHITECTURE.md` §9: no shell, and detection has no reason to run the binary either.

    Asserted against the source, because a subprocess call added later would still pass every
    behavioural test above.
    """
    source = Path(environment.__file__).read_text(encoding="utf-8")
    for forbidden in ("subprocess", "os.system", "shell=True", "popen"):
        assert forbidden not in source.lower(), f"{forbidden} in a detection-only module"


# --- privacy (NFR-007) ------------------------------------------------------------------------


def test_the_candidate_description_leaks_no_user_path(tmp_path: Path) -> None:
    """`NFR-007`. The user directory sits under the user's home, so logging it leaks a
    username into a file that may be attached to a bug report.

    The source label carries the useful fact — which candidate was chosen — without the path.
    """
    user_copy = tmp_path / "seans-secret-home" / "ytdlp"
    user_copy.mkdir(parents=True)

    description = describe_candidates(ytdlp_candidates(user_copy))
    assert "seans-secret-home" not in description
    assert str(user_copy) not in description
    assert "user-managed" in description and "baseline" in description


def test_the_ffmpeg_summary_leaks_no_override_path(tmp_path: Path) -> None:
    """The only path in play when ffmpeg is missing is one the user typed (`NFR-007`)."""
    override = tmp_path / "home" / "sean" / "ffmpeg-custom"
    report = find_ffmpeg(override=override)
    assert str(override) not in report.summary()
    assert "sean" not in report.summary()


def test_reports_are_immutable_and_carry_tuples() -> None:
    """These cross the process boundary to the worker (`ARC-002`), like every other value."""
    report = FfmpegReport(path=None, source="x", unavailable_features=FFMPEG_DEPENDENT_FEATURES)
    with pytest.raises(AttributeError):
        report.path = Path("/elsewhere")  # type: ignore[misc]
    assert isinstance(report.unavailable_features, tuple)

    candidate = ytdlp_candidates()[0]
    with pytest.raises(AttributeError):
        candidate.source = "elsewhere"  # type: ignore[misc]


# --- the pinned baseline (OPS-002, T033-R1) ---------------------------------------------------


def test_the_restated_pin_matches_pyproject() -> None:
    """`BASELINE_YTDLP_VERSION` restates the pin so a frozen build can check itself.

    Restating it is only acceptable because this test makes the duplication non-silent: bumping
    `pyproject.toml` without bumping the constant would otherwise leave the frozen probe
    asserting the *old* version and failing every build with a message blaming the artifact.

    The pin is parsed from `pyproject.toml` rather than restated a third time here.
    """
    import tomllib

    root = Path(__file__).parents[2]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    pins = [d for d in data["project"]["dependencies"] if d.replace("_", "-").startswith("yt-dlp")]

    assert len(pins) == 1, f"expected exactly one yt-dlp dependency, found {pins}"
    assert "==" in pins[0], f"OPS-002 requires an exact pin, not {pins[0]!r}"
    pinned = pins[0].split("==", 1)[1].strip()
    assert pinned == environment.BASELINE_YTDLP_VERSION


def test_the_installed_baseline_is_the_pinned_one() -> None:
    """The constant is only useful if it describes what is actually installed."""
    from tracks_and_trails.downloader.environment import normalise_version

    installed = importlib.metadata.version("yt-dlp")
    assert normalise_version(installed) == normalise_version(environment.BASELINE_YTDLP_VERSION)


@pytest.mark.parametrize(
    ("left", "right", "equal"),
    [
        ("2026.7.4", "2026.07.04", True),
        ("2026.07.04", "2026.7.4", True),
        ("2026.7.4", "2026.7.5", False),
        ("2026.7.4", "2025.7.4", False),
        ("2026.7", "2026.7.0", False),
    ],
)
def test_versions_compare_by_value_not_by_spelling(left: str, right: str, equal: bool) -> None:
    """The pin reads `2026.7.4`; the package reports `2026.07.04`. Same release.

    Expectations are transcribed from that fact rather than from the implementation
    (`docs/project/TESTING.md` §13). The inequality cases matter more than the equality one: a
    normalisation that returned a constant would satisfy the first two and is the failure mode
    worth guarding.
    """
    from tracks_and_trails.downloader.environment import normalise_version

    assert (normalise_version(left) == normalise_version(right)) is equal


def test_a_non_numeric_version_does_not_crash_the_comparison() -> None:
    """A patched or development build must fail the check loudly, not raise inside the probe."""
    from tracks_and_trails.downloader.environment import normalise_version

    assert normalise_version("2026.7.4dev") != normalise_version("2026.7.4")


# --- the build's own ffmpeg (`T-319`) ----------------------------------------------------------


def test_a_source_checkout_has_no_bundled_ffmpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing here runs in development, and `sys.frozen` is the whole of the test.

    `OPS-001` bundles ffmpeg in the *artifact*. A checkout that started reporting one would mean
    the search order below was being exercised by developers and by nobody it was written for.
    """
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert environment.bundled_ffmpeg() is None


def test_a_frozen_build_finds_the_ffmpeg_in_its_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**The layout a real build produces**, which is not the one this test used to assume.

    It planted the file beside a fake `sys.executable` and passed — agreeing with the code and
    with nothing else. PyInstaller 6 puts a one-dir bundle under `_internal/`, so a `binaries`
    destination of `"."` lands there: measured on Windows as `_internal\ffmpeg.exe`, one level
    below where `bundled_ffmpeg` was looking (`T-319`).
    """
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    bundle = tmp_path / "_internal"
    bundle.mkdir()
    shipped = bundle / name
    shipped.write_text("")
    shipped.chmod(0o755)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "tracks-and-trails"))
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)

    assert environment.bundled_ffmpeg() == shipped


def test_a_frozen_build_still_finds_one_beside_the_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second candidate, kept rather than dropped.

    It costs one `is_file()` and it is where an older PyInstaller — or a hand-assembled tree —
    puts it. Here `_MEIPASS` exists and holds no ffmpeg, so the fallback is what answers.
    """
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    bundle = tmp_path / "_internal"
    bundle.mkdir()
    shipped = tmp_path / name
    shipped.write_text("")
    shipped.chmod(0o755)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "tracks-and-trails"))
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)

    assert environment.bundled_ffmpeg() == shipped


def test_a_frozen_build_without_one_reports_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Linux artifact ships no ffmpeg (`OPS-001`), and must not claim to."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "tracks-and-trails"))

    assert environment.bundled_ffmpeg() is None


def test_the_bundled_copy_is_preferred_over_one_on_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**The ordering this task exists for** (`T-319`).

    A user with their own newer ffmpeg installed must not silently displace the build this
    artifact was tested against: a different build is a different set of encoders, and `OPS-001`
    bundles one precisely so the feature works without the user arranging anything.
    """
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    shipped = tmp_path / "app" / name
    shipped.parent.mkdir()
    shipped.write_text("")
    shipped.chmod(0o755)

    elsewhere = tmp_path / "path"
    elsewhere.mkdir()
    other = elsewhere / name
    other.write_text("")
    other.chmod(0o755)

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(shipped.parent / "tracks-and-trails"))

    report = environment.find_ffmpeg(search_path=str(elsewhere))
    assert report.path == shipped, "the copy on PATH won over the one that shipped"
    assert "bundled" in report.source


def test_an_explicit_override_still_wins_over_the_bundled_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The user saying which one they mean outranks the build's own (`OPS-001`)."""
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    shipped = tmp_path / "app" / name
    shipped.parent.mkdir()
    shipped.write_text("")
    shipped.chmod(0o755)

    chosen = tmp_path / "chosen" / name
    chosen.parent.mkdir()
    chosen.write_text("")
    chosen.chmod(0o755)

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(shipped.parent / "tracks-and-trails"))

    report = environment.find_ffmpeg(override=chosen)
    assert report.path == chosen
    assert "override" in report.source


def test_a_build_with_no_bundled_copy_still_finds_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`REQ-024`'s ordinary Linux case, unchanged by any of the above."""
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    elsewhere = tmp_path / "path"
    elsewhere.mkdir()
    (elsewhere / name).write_text("")
    (elsewhere / name).chmod(0o755)

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "tracks-and-trails"))

    report = environment.find_ffmpeg(search_path=str(elsewhere))
    assert report.path == elsewhere / name
    assert report.source == "PATH"
