"""The per-user redirect covers every consumer, and keeps covering them (`T123-R2`).

`ai/TESTING.md` §5's rule existed with no mechanism behind it for the whole project. The mechanism
is `tests/user_directories.py`; these are the tests that stop it from quietly stopping.
"""

from __future__ import annotations

import ast
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
