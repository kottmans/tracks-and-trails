"""The tag-to-version rule, driven through the cases a release only produces once (`T-320`).

`REL-003` says a release commit sets `__version__ = "X.Y.Z"` and is tagged `vX.Y.Z`. Both halves
of that are checkable and neither is visible in a diff, which is why the rule is a function rather
than a paragraph in `docs/RELEASE.md`.

**A tag is the one artifact in this project that cannot be quietly corrected.** A wrong commit is
amended, a wrong release page is edited; a tag somebody has already installed from is a name in the
wild. So the cases below are the ones a release gets exactly one attempt at.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
TOOL = REPOSITORY / "tools" / "version_tag_check.py"


def load() -> ModuleType:
    """Load the tool by path, the way `test_job_duration_report.py` loads its own.

    `tools/` is not a package and is not in `mypy`'s `files`, so a plain import is both an
    unresolvable module and a source of `Any`. This is the pattern the project already uses, and
    the first version of this file did not — a `sys.path` insert passed `pytest` and failed
    `mypy` on both platforms, which is what a required gate is for.
    """
    specification = importlib.util.spec_from_file_location("version_tag_check", TOOL)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


tool = load()
check = tool.check
installed_version = tool.installed_version
main = tool.main


def test_a_matching_tag_and_version_is_publishable() -> None:
    """The positive control: without it, every assertion below passes a checker that
    always fails."""
    assert check("v0.1.0", "0.1.0") is None
    assert check("v1.0.0", "1.0.0") is None
    assert check("v12.4.37", "12.4.37") is None


def test_a_development_version_cannot_be_tagged() -> None:
    """**The defect that ships silently.** `0.1.0.dev0` tagged `v0.1.0` releases a build that
    reports itself as a development version for as long as it exists.

    `main` carries `.devN` by design, so this is not a hypothetical: it is the state of the
    repository on every day except the release commit, and `test_the_repository_as_it_stands_today`
    below asserts exactly that.
    """
    problem = check("v0.1.0", "0.1.0.dev0")
    assert problem is not None
    assert "development build" in problem


def test_a_tag_and_version_that_disagree_are_refused() -> None:
    """`--version` would tell a user something the release page does not."""
    problem = check("v0.2.0", "0.1.0")
    assert problem is not None
    assert "same number" in problem


@pytest.mark.parametrize(
    "tag",
    [
        "0.1.0",  # no `v`
        "v0.1",  # two components; REL-003 names three
        "v0.1.0.0",  # four
        "v0.1.0-rc1",  # a pre-release spelling this project has not decided
        "v0.1.0+build7",  # build metadata, likewise
        "release-0.1.0",
        "v",
        "",
    ],
)
def test_a_tag_that_is_not_a_release_tag_is_refused(tag: str) -> None:
    """**The shape is refused before the number is compared**, so an undecided spelling cannot
    ship on the grounds that its digits happened to line up.

    `v0.1.0-rc1` is the one worth naming: a pre-release channel is a real thing a project may want
    and `REL-003` did not take it. Accepting the tag here would be this checker deciding it.
    """
    problem = check(tag, "0.1.0")
    assert problem is not None
    assert "not a release tag" in problem


def test_the_repository_as_it_stands_today_cannot_be_tagged() -> None:
    """A live positive control, not a constructed one (`T-320`).

    `main` is supposed to carry `.devN`. If this ever passes, either a release commit is checked
    out — in which case the tag is the next step and this test has told the truth — or somebody has
    dropped the suffix on `main`, which is the mistake `REL-003` exists to prevent.
    """
    version = installed_version()
    assert check(f"v{version.split('.dev')[0]}", version) is not None, (
        f"__version__ is {version!r}, which is a released version sitting on main. REL-003 keeps "
        f"the .devN suffix between releases"
    )


def test_the_command_line_reports_and_exits() -> None:
    """Both directions, because a checker that cannot fail is not a gate."""
    assert main(["--tag", "v0.1.0", "--version", "0.1.0"]) == 0
    assert main(["--tag", "v0.1.0", "--version", "0.1.0.dev0"]) == 1


def test_the_tool_runs_as_a_script_against_this_checkout() -> None:
    """The form `T-324`'s workflow will invoke, run as a subprocess rather than imported.

    An import-time mistake — `installed_version` inserting the wrong path, say — is invisible to
    every test above, because the test process already has the package importable.
    """
    finished = subprocess.run(
        [sys.executable, "tools/version_tag_check.py", "--tag", "v0.1.0"],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )
    assert finished.returncode == 1, finished.stdout + finished.stderr
    assert "development build" in finished.stderr
