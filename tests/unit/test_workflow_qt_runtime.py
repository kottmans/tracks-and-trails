"""A Linux job that installs this project must also provide Qt's runtime libraries.

**This exists because the rule was kept by accident until it wasn't.** `ci.yml` has installed
`libegl1` and friends on hosted runners since `T-006`; `ytdlp-canary.yml` and `flake-soak.yml`
never needed to, because Linux always ran on the maintainer's Fedora machines where those
libraries are present. `OPS-012`'s 2026-09-08 amendment moved Linux to `ubuntu-latest`, and the
canary's next run died on `libEGL.so.1: cannot open shared object file`.

**The failure is worse than it sounds, which is why this is a test rather than a note.** The
missing library does not surface at install time. It surfaces inside pytest as an
`INTERNALERROR` while collecting, so it reads as a broken suite rather than a broken image — the
canary had been red since 2026-09-07 and nobody could tell whether it had found real yt-dlp
drift.

The rule is deliberately about **installing the project**, not about running Qt tests: this
project depends on PySide6, so any environment that pip-installs it and then runs anything needs
Qt's libraries. `prose.yml` installs `pytest` alone and is correctly exempt.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"

#: Installing this project pulls PySide6, which links these at import time.
QT_MARKERS = ("libegl1", "libEGL.so.1")

#: What "installs this project" looks like. `pip install pytest` alone does not qualify.
INSTALLS_PROJECT = re.compile(r"pip install .*-e\s+[\"']?\.", re.I)

#: A job pinned to Windows labels never reaches this rule.
WINDOWS_ONLY = re.compile(r"windows", re.I)


def workflow_files() -> list[Path]:
    found = sorted(WORKFLOWS.glob("*.yml"))
    assert found, "no workflows found; the path this test reads has moved"
    return found


def steps_of(job: dict[str, object]) -> list[dict[str, object]]:
    """The job's step mappings. YAML gives back `object`, so the shape is checked, not assumed."""
    steps = job.get("steps")
    if not isinstance(steps, list):
        return []
    return [step for step in steps if isinstance(step, dict)]


def run_text(job: dict[str, object]) -> str:
    return "\n".join(str(step.get("run", "")) for step in steps_of(job))


def is_windows_only(job: dict[str, object]) -> bool:
    runs_on = job.get("runs-on", "")
    rendered = (
        " ".join(str(part) for part in runs_on) if isinstance(runs_on, list) else str(runs_on)
    )
    # A matrix naming both platforms is not Windows-only, whatever the expression says.
    if "matrix" in rendered and WINDOWS_ONLY.search(str(job.get("strategy", ""))):
        return "ubuntu" not in str(job.get("strategy", "")).lower()
    return bool(WINDOWS_ONLY.search(rendered)) and "ubuntu" not in rendered.lower()


@pytest.mark.parametrize("path", workflow_files(), ids=lambda p: p.name)
def test_a_job_that_installs_the_project_provides_qt_libraries(path: Path) -> None:
    """Every job that pip-installs this project on Linux installs or verifies Qt's libraries."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    for name, job in (document.get("jobs") or {}).items():
        if not isinstance(job, dict) or is_windows_only(job):
            continue
        commands = run_text(job)
        if not INSTALLS_PROJECT.search(commands):
            continue
        assert any(marker in commands for marker in QT_MARKERS), (
            f"{path.name}:{name} installs this project but never provides Qt's runtime "
            f"libraries. On a hosted Linux image that fails inside pytest as an INTERNALERROR "
            f"on libEGL.so.1, which reads as a broken suite. Copy ci.yml's "
            f"'Install Qt runtime libraries' step."
        )


def test_the_rule_has_something_to_check() -> None:
    """Guards the parametrisation: a filter that matched nothing would pass silently."""
    installing = [
        path.name
        for path in workflow_files()
        for job in (yaml.safe_load(path.read_text(encoding="utf-8")).get("jobs") or {}).values()
        if isinstance(job, dict) and INSTALLS_PROJECT.search(run_text(job))
    ]
    assert len(installing) >= 3, (
        f"expected several project-installing workflows, found {installing}"
    )


def test_a_qt_free_workflow_is_not_required_to_install_qt() -> None:
    """`prose.yml` installs `pytest` alone, and the rule must not drag it in."""
    document = yaml.safe_load((WORKFLOWS / "prose.yml").read_text(encoding="utf-8"))
    commands = "\n".join(run_text(job) for job in document["jobs"].values())
    assert "pytest" in commands
    assert not INSTALLS_PROJECT.search(commands), "prose.yml now installs the project"
    assert not any(marker in commands for marker in QT_MARKERS)
