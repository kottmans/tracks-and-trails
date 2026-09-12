"""One version's changelog section, which becomes a release body (`T-324`).

Three ways to be quietly wrong: the wrong section, an empty section, and *no* section reported as
an empty one. The third is the one that matters — a draft release with an empty body is worse than
a workflow that stopped, because a human then publishes it.

**There is no `CHANGELOG.md` in this repository yet.** `docs/RELEASE.md` makes creating it a
release-commit step, so every case here builds its own text rather than reading the project's.
That is also why the missing-file case is asserted: it is the current state.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

import pytest

REPOSITORY: Final = Path(__file__).resolve().parents[2]
TOOL: Final = REPOSITORY / "tools" / "changelog_section.py"


def load() -> ModuleType:
    specification = importlib.util.spec_from_file_location("changelog_section", TOOL)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


tool = load()

KEEP_A_CHANGELOG = """\
# Changelog

## [Unreleased]

- something in flight

## [0.2.0] - 2026-10-01

### Added

- a later release, so the first section is not simply the last thing in the file

## [0.1.0] - 2026-09-12

### Added

- the first release

### Fixed

- a thing
"""


@pytest.mark.parametrize(
    ("heading", "version"),
    [
        ("## [0.1.0] - 2026-09-12", "0.1.0"),
        ("## 0.1.0", "0.1.0"),
        ("## v0.1.0", "0.1.0"),
        ("## [v0.1.0] (2026-09-12)", "0.1.0"),
        ("## [0.1.0rc1]", "0.1.0rc1"),
        ("## [0.1.0.dev0]", "0.1.0.dev0"),
    ],
)
def test_a_version_heading_is_recognised_however_it_is_decorated(
    heading: str, version: str
) -> None:
    """Tolerant about the decoration, because `## [0.1.0] - date` and `## 0.1.0` name the same
    release and a tool that accepted only one would be a style rule pretending to be a check."""
    body, complaint = tool.section_for(version, f"# Changelog\n\n{heading}\n\n- a note\n")
    assert complaint is None, complaint
    assert body == "- a note"


def test_the_body_stops_at_the_next_version() -> None:
    """The section for `0.1.0` must not carry `0.2.0`'s notes into a release body."""
    body, complaint = tool.section_for("0.1.0", KEEP_A_CHANGELOG)
    assert complaint is None, complaint
    assert "the first release" in body
    assert "a later release" not in body, "the section ran into the one above it"
    assert "something in flight" not in body, "the Unreleased section leaked in"


def test_an_unreleased_section_is_not_mistaken_for_a_version() -> None:
    """`## [Unreleased]` is the conventional top section and names no version."""
    assert "Unreleased" not in tool.sections(KEEP_A_CHANGELOG)
    assert set(tool.sections(KEEP_A_CHANGELOG)) == {"0.1.0", "0.2.0"}


@pytest.mark.parametrize(
    "heading",
    [
        "## 2026-09-12",  # a date, which is what a changelog heading often looks like
        "## 1.0",  # two parts, not a version this project can tag (REL-003 is SemVer)
        "## 12",
        "## [Unreleased]",
        "## Notes",
        "## 0.1",
    ],
)
def test_a_heading_that_is_not_a_version_is_not_treated_as_one(heading: str) -> None:
    """**The guard a mutation survived.** Dropping the anchored three-part check left every test
    passing, because the cases above were never written: the existing ones all asked for a
    version that simply was not present, which fails either way.

    A date heading matching would make the *date* a release, and `## 1.0` would let a two-part
    number claim a section `REL-003`'s SemVer can never tag.
    """
    assert tool.sections(f"# Changelog\n\n{heading}\n\n- a note\n") == {}


def test_a_similar_version_is_not_accepted_for_the_one_asked_for() -> None:
    """**The anchoring case.** `0.1.1` must not satisfy a request for `0.1.0`, and `0.1.10` must
    not either — a substring match would hand a release the wrong notes."""
    text = "# Changelog\n\n## [0.1.10]\n\n- ten\n\n## [0.1.1]\n\n- one\n"
    body, complaint = tool.section_for("0.1.0", text)
    assert body is None
    assert complaint is not None and "no section for 0.1.0" in complaint
    assert "0.1.1" in complaint and "0.1.10" in complaint, (
        "the complaint should list what it did find, so the fix is obvious"
    )


def test_a_missing_section_is_told_apart_from_an_empty_one() -> None:
    """Two different mistakes with two different fixes, and the second is the one a release body
    would carry silently."""
    absent, absent_complaint = tool.section_for("9.9.9", KEEP_A_CHANGELOG)
    assert absent is None and absent_complaint is not None
    assert "no section" in absent_complaint

    empty, empty_complaint = tool.section_for(
        "0.1.0", "# Changelog\n\n## [0.1.0]\n\n## [0.0.9]\n\n- older\n"
    )
    assert empty is None and empty_complaint is not None
    assert "is empty" in empty_complaint, empty_complaint
    assert "worse than a workflow that stopped" in empty_complaint


def test_the_cli_reports_a_missing_changelog_as_the_missing_file_it_is(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The repository's current state: `docs/RELEASE.md` makes creating it a release-commit step.

    Reported as an absent file rather than as an empty body, because those need different fixes.
    """
    assert tool.main(["--version", "0.1.0", "--changelog", str(tmp_path / "nope.md")]) == 1
    assert "does not exist" in capsys.readouterr().err


def test_the_cli_prints_only_the_body(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """It is piped straight into `gh release create --notes-file`, so anything extra on stdout
    ends up on the release page."""
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(KEEP_A_CHANGELOG, encoding="utf-8")
    assert tool.main(["--version", "0.1.0", "--changelog", str(changelog)]) == 0
    printed = capsys.readouterr().out
    assert printed.startswith("### Added")
    assert "0.2.0" not in printed and "Changelog" not in printed


def test_a_leading_v_is_accepted_because_a_tag_carries_one(tmp_path: Path) -> None:
    """The workflow passes `${GITHUB_REF_NAME#v}`, but a human running this by hand will paste
    the tag. Both mean the same release."""
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(KEEP_A_CHANGELOG, encoding="utf-8")
    assert tool.main(["--version", "v0.1.0", "--changelog", str(changelog)]) == 0


def test_the_tool_runs_as_a_script_against_this_checkout() -> None:
    """The form the workflow invokes, run as a subprocess rather than imported — an import-time
    mistake is invisible to every test above."""
    import subprocess

    finished = subprocess.run(
        [sys.executable, "tools/changelog_section.py", "--version", "0.1.0"],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )
    # No CHANGELOG.md exists yet, so the honest outcome is a named refusal.
    assert finished.returncode == 1, finished.stdout + finished.stderr
    assert "does not exist" in finished.stderr
