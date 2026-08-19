"""The formatter and the type-checker are the versions `pyproject.toml` declares (`T-269`).

**Why this is a test and not a note in the setup instructions.** `T-266` spent a full `STARBASE`
round — one of the scarcest things this project has, since `OPS-003` means nobody logs in to that
machine — because the local checkout formatted at Ruff 0.16.0 while CI rebuilt its environment at
0.16.3, and the two versions disagree about where to break a multiple-exception clause. Every
local gate was green. The failure was reported by the Windows job, after the queue, before the
measurement the round existed to take could run.

**A floor cannot prevent that and an exact pin alone only half-prevents it.** `ruff>=0.9` is
satisfied by whatever is already installed, so `pip install -e ".[dev]"` upgraded nothing; `==`
fixes the *install*. What `==` does not fix is an environment nobody reinstalled — a checkout from
before the pin, a virtualenv built against an older `pyproject.toml`, a tool installed globally
and shadowing the venv. In every one of those the declaration is right and the running tool is
not, which is exactly the state that was expensive.

So this asserts the thing that actually matters: **the tools in the environment running the suite
are the tools the file declares.** It fails on the developer's machine, in a second, instead of on
the Windows runner, after half an hour.

**It reads the declaration rather than repeating it.** A test carrying its own copy of the version
number would be the second place a number lives, and the two would drift — the defect this task
exists to close, reproduced inside its own gate. `pyproject.toml` is parsed; nothing here knows
what the versions are.
"""

from __future__ import annotations

import re
import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pytest

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"

#: The tools whose version has to match exactly. Both are **gates**: they decide whether a change
#: is allowed to land, and a gate that behaves differently in two places is two gates. The rest of
#: the `dev` extra is deliberately not here — `pytest` disagreeing by a patch release changes no
#: verdict, and pinning everything would turn every dependency bump into a suite failure.
PINNED_TOOLS = ("ruff", "mypy")


def _declared() -> dict[str, str]:
    """The `name == version` pins in the `dev` extra, as a mapping."""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    dev = data["project"]["optional-dependencies"]["dev"]
    pins: dict[str, str] = {}
    for requirement in dev:
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s;]+)", requirement.strip())
        if match is not None:
            pins[match.group(1).lower()] = match.group(2)
    return pins


def test_both_gates_are_pinned_rather_than_floored() -> None:
    """The positive control: everything below passes vacuously over a pin that is not there.

    If somebody relaxes `ruff==0.16.3` back to `ruff>=0.9`, `_declared()` stops returning it and
    the comparison test would find nothing to compare and pass. That is precisely the state
    `T266-R2` reported, so it must fail loudly rather than quietly.
    """
    declared = _declared()
    unpinned = [tool for tool in PINNED_TOOLS if tool not in declared]

    assert not unpinned, (
        f"{unpinned} are no longer pinned with `==` in pyproject.toml's dev extra. A floor is "
        "satisfied by whatever is already installed, so the local gate and the CI gate stop "
        "being the same gate — which is what T-269 was filed for."
    )


@pytest.mark.parametrize("tool", PINNED_TOOLS)
def test_the_installed_tool_is_the_declared_one(tool: str) -> None:
    """What is actually running, against what the file says should be.

    `importlib.metadata` reads the environment this interpreter imports from, which is the
    environment `ruff` and `mypy` run in under CI and under `pytest` alike. Asking the tools
    themselves through a subprocess would measure `PATH` instead, and `PATH` is not what the
    gates are installed from.
    """
    declared = _declared()[tool]
    try:
        installed = version(tool)
    except PackageNotFoundError:  # pragma: no cover - a dev extra that was never installed
        pytest.fail(
            f"{tool} is not installed in this environment, so its gate cannot run at all. "
            'Install the dev extra: pip install -e ".[dev]"'
        )

    assert installed == declared, (
        f"{tool} {installed} is installed and pyproject.toml declares {declared}. These decide "
        "whether a change may land, and two versions are two gates: T-266 lost a whole STARBASE "
        "round to a 0.16.0/0.16.3 formatter split that every local check called green. "
        'Reinstall the dev extra: pip install -e ".[dev]"'
    )
