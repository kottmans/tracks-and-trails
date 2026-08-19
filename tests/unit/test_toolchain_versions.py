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

## Two invariants, because `PATH` is the production boundary and metadata is not

`T269-R1` found the first version of this file measuring the wrong thing. It compared
`importlib.metadata.version()` — the **distribution installed in the interpreter running pytest** —
while `ai/TESTING.md` §4 and every CI step invoke bare `ruff` and `mypy`, which resolve through
`PATH`. The reviewer put different executables first on `PATH`; all three tests passed while
`ruff --version` reported the injected one. The docstring above had explicitly listed *"a tool
installed globally and shadowing the venv"* as a case this file covers, and it did not.

So there are two separate invariants here, and they are stated separately because they can
disagree — the disagreement **is** the defect:

1. **What `pip install -e ".[dev]"` reached** — `importlib.metadata`. This is the install's own
   result, and the one an exact pin controls.
2. **What the documented commands actually run** — the bare `ruff` and `mypy` on `PATH`. This is
   what decides whether a change lands, and it is the authoritative one.
"""

from __future__ import annotations

import re
import shutil
import subprocess
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
def test_the_installed_distribution_is_the_declared_one(tool: str) -> None:
    """Invariant 1: what the install reached, which is what the exact pin controls.

    `importlib.metadata` reads the distribution in the environment this interpreter imports from.
    That is the thing `pip install -e ".[dev]"` acts on, so this is the assertion that fails when
    somebody has not reinstalled after a pin moved.

    **It is not sufficient on its own** (`T269-R1`) — it says nothing about which executable the
    documented commands resolve to. `test_the_command_the_gates_run_is_the_declared_one` is that
    half, and the two are kept apart because a disagreement between them is exactly the shadowing
    defect.
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


def _version_reported_by(command: str) -> str:
    """The version `command --version` prints, resolved the way a shell resolves it.

    No `sys.executable`, no `.venv/bin` prefix, no `-m`: `ai/TESTING.md` §4 says `ruff check .` and
    `mypy src`, and CI's steps say the same. Whatever those words resolve to is what gates this
    project, so that is what gets measured.
    """
    reported = subprocess.run(
        [command, "--version"], capture_output=True, text=True, check=True
    ).stdout
    found = re.search(r"(\d+\.\d+(?:\.\d+)?)", reported)
    assert found is not None, f"`{command} --version` printed no version: {reported!r}"
    return found.group(1)


@pytest.mark.parametrize("tool", PINNED_TOOLS)
def test_the_command_the_gates_run_is_the_declared_one(tool: str) -> None:
    """Invariant 2, and the authoritative one: what `ruff` and `mypy` resolve to on `PATH`.

    **`T269-R1`.** The first version of this file checked installed metadata only, and a reviewer
    put different executables first on `PATH`: every assertion passed while the bare command
    selected the injected one. A gate that approves a different binary from the one it gates with
    is the same class as `T258-R7`'s probe patching a class production never constructs — the
    check runs, reports success, and is measuring something else.

    The failure message names both resolutions, because *"0.16.0 is installed"* and *"the `ruff`
    on your `PATH` is 0.16.0"* have different fixes: one is a reinstall, the other is an
    environment that is not the one you think you are in.
    """
    declared = _declared()[tool]
    resolved = shutil.which(tool)
    assert resolved is not None, (
        f"no `{tool}` on PATH, so the command `ai/TESTING.md` §4 documents cannot run at all. "
        'Install the dev extra and activate its environment: pip install -e ".[dev]"'
    )

    assert _version_reported_by(tool) == declared, (
        f"`{tool} --version` reports {_version_reported_by(tool)} and pyproject.toml declares "
        f"{declared}. The command resolves to {resolved}, and the distribution installed for this "
        f"interpreter is {version(tool)} — if those two differ, something ahead of the virtualenv "
        f"on PATH is shadowing it, and the gate you run is not the gate CI runs."
    )
