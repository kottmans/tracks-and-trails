"""The per-user redirect covers every consumer, and keeps covering them (`T123-R2`).

`ai/TESTING.md` §5's rule existed with no mechanism behind it for the whole project. The mechanism
is `tests/user_directories.py`; these are the tests that stop it from quietly stopping.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import platformdirs

from tests import user_directories

#: `src/`, found from this file rather than from the working directory.
SOURCE = Path(__file__).resolve().parents[2] / "src" / "tracks_and_trails"


def test_every_platformdirs_consumer_is_redirected() -> None:
    """The list is re-derived from the source, so a new consumer cannot be missed.

    **This is the test `T214-R1` asks for.** A redirect is a guard, and a guard that names its
    subjects by hand stops guarding the moment somebody adds one — silently, because nothing
    fails. Deriving the truth from `src/` and comparing makes the omission the failure.

    **Parsed rather than grepped, and the first version of this test is why.** It matched
    `^from platformdirs import (\\w+)`, which missed `app.py` because that import is *indented
    inside a function* — a guard proved against one spelling, in the test written to stop guards
    being proved against one spelling. `ast` sees the import wherever it is, under whatever
    formatting, including aliases and parenthesised lists.
    """
    found: set[tuple[str, str]] = set()
    for path in SOURCE.rglob("*.py"):
        module = ".".join(("tracks_and_trails", *path.relative_to(SOURCE).with_suffix("").parts))
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module == "platformdirs":
                found.update((module, alias.name) for alias in node.names)

    missing = found - set(user_directories.CONSUMERS)
    assert not missing, (
        f"{sorted(missing)} import a platformdirs directory and are not in CONSUMERS, so a test "
        "that reaches them writes to the real machine (`ai/TESTING.md` §5)"
    )

    stale = set(user_directories.CONSUMERS) - found
    assert not stale, (
        f"{sorted(stale)} are listed in CONSUMERS but no longer import what they claim to — the "
        "list is describing a shape the source has moved on from"
    )


def test_the_redirect_answers_inside_the_given_root(tmp_path: Path) -> None:
    """Each directory family lands in its own subdirectory of the per-test root.

    The autouse fixture has already run for this test, so what is asserted here is the state
    every other test in the suite is also in.
    """
    for function, subdirectory in (
        (platformdirs.user_cache_dir, "cache"),
        (platformdirs.user_config_dir, "config"),
        (platformdirs.user_data_dir, "data"),
        (platformdirs.user_downloads_dir, "downloads"),
    ):
        answered = Path(function())
        assert answered.parts[-1] == subdirectory, f"{function.__name__} answered {answered}"
        assert tmp_path.parts[1] != "home" or "platform" in answered.parts, (
            f"{function.__name__} answered {answered}, which is not inside a per-test root"
        )

    # The slug is still appended when one is asked for, because `cache_root()` and its siblings
    # are documented as `user_*_dir/tracksandtrails` and callers build on that shape.
    assert Path(platformdirs.user_cache_dir("tracksandtrails")).parts[-1] == "tracksandtrails"


def test_a_consumer_module_calls_the_redirected_function() -> None:
    """The module's *own* binding is patched, not just `platformdirs`.

    Every consumer does `from platformdirs import …`, which copies the reference at import. A
    redirect that only replaced `platformdirs.user_cache_dir` would leave all of them calling the
    original — which is the defect this module exists to avoid, so it gets an assertion rather
    than a comment.
    """
    from tracks_and_trails.core import paths

    assert "platform" in paths.cache_directory().parts, (
        f"core.paths.cache_directory() answered {paths.cache_directory()}, outside the per-test "
        "root — its own `user_cache_dir` binding is not redirected"
    )


# --- T-230: the half a monkeypatch cannot reach ------------------------------------------------


def test_a_spawned_child_resolves_its_directories_inside_the_test(tmp_path: Path) -> None:
    """**The redirect reaches a process the test spawns**, which patching cannot (`T-230`).

    Measured before this existed: `tests/integration` left **62** files under the real
    `user_cache_dir`, all job logs, from nine files that spawn children. A child inherits its
    parent's environment, so one export here covers all nine rather than nine `env=` dictionaries.

    **Asserted through a real child**, because that is the boundary in question — an in-process
    check would pass against the patching that was already there and prove nothing new. The child
    imports `platformdirs` for itself, exactly as a spawned worker does.

    The autouse `_per_user_directories` fixture has already run, so the environment under test is
    the one every test gets; nothing here arranges it.
    """
    answer = subprocess.run(
        [
            sys.executable,
            "-c",
            "import platformdirs, sys; sys.stdout.write(platformdirs.user_cache_dir('x'))",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    resolved = Path(answer.stdout.strip())
    assert str(resolved).startswith(str(tmp_path)), (
        f"a spawned child resolved its cache directory to {resolved}, outside this test's "
        f"{tmp_path}. It is writing to the developer's machine, which ai/TESTING.md §5 forbids"
    )


def test_the_child_environment_and_the_patched_modules_name_the_same_root(tmp_path: Path) -> None:
    """The two halves must agree, or a child and its parent disagree about where anything is.

    **The failure this prevents is not a crash.** A parent that writes its queue database to one
    directory while its worker reads a cache from another produces a test that passes and an
    application whose two halves are looking at different disks. Nothing raises.

    Compared as *paths*, not as strings: `redirect` hands `platformdirs` a function returning
    `root / subdirectory / appname`, and the environment gets `root / subdirectory`.

    **The variable names are written out here, not read from `_CHILD_ENVIRONMENT`.** The first
    version of this test iterated that dict, so deleting the two Windows entries deleted the
    assertions about them and the mutant passed — a guard proved against itself. `platformdirs`
    consults `XDG_*` only on POSIX and `WIN_PD_OVERRIDE_*` only on Windows, so **both families are
    required**; `T-131` is the round where setting one of them passed on Linux and failed on the
    runner.
    """
    assert set(user_directories._CHILD_ENVIRONMENT) == {
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "WIN_PD_OVERRIDE_APPDATA",
        "WIN_PD_OVERRIDE_LOCAL_APPDATA",
    }, (
        "the child environment no longer exports both families. platformdirs reads XDG_* only on "
        "POSIX and WIN_PD_OVERRIDE_* only on Windows, so dropping either leaves that platform's "
        "spawned children writing to the real machine"
    )

    for variable, subdirectory in user_directories._CHILD_ENVIRONMENT.items():
        exported = os.environ.get(variable)
        assert exported is not None, f"{variable} is not exported, so a child cannot inherit it"
        assert Path(exported).parent == tmp_path / "platform", (
            f"{variable} points at {exported}, which is not under this test's redirect root"
        )
        assert Path(exported).name == subdirectory

    # The POSIX three are the ones platformdirs reads here; each must match what the in-process
    # patch answers for the same directory, or the halves have drifted apart.
    for variable, function in (
        ("XDG_CACHE_HOME", platformdirs.user_cache_dir),
        ("XDG_CONFIG_HOME", platformdirs.user_config_dir),
        ("XDG_DATA_HOME", platformdirs.user_data_dir),
    ):
        assert Path(function()) == Path(os.environ[variable]), (
            f"{variable} and the patched {function.__name__} disagree: "
            f"{os.environ[variable]} against {function()}"
        )
