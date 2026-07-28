"""Run T-026's mutation classes against the windows_desktop suite, on a real Windows desktop.

`T-040` has required this since it was filed and it has never run anywhere: the GitHub job proves
the tests pass, which is not evidence about a mutation nobody executed.

MUST be run from the RDP/console session. Over SSH there is no window station, so Qt cannot
create a window and every result would be meaningless rather than merely wrong.

Each mutation is a pytest plugin, so the checkout is never modified and a crash cannot leave a
half-mutated file behind. Run it from the repository root.
"""

import os
import subprocess
import sys
from pathlib import Path

# The repository is wherever this was launched from, and the interpreter is whichever one is
# running it — both stated by the caller rather than guessed from this file's location, which is
# what the first version got wrong (it lives beside the checkout, not inside it).
MUTATIONS = Path(__file__).resolve().parent
ROOT = Path.cwd()
PYTHON = Path(sys.executable)

if not (ROOT / "pyproject.toml").is_file():
    raise SystemExit(f"run this from the repository root; {ROOT} has no pyproject.toml")
if ".venv" not in str(PYTHON):
    raise SystemExit(f"run this with the project venv's python, not {PYTHON}")

CASES = [
    ("baseline, unmutated", None, "pass"),
    # The positive control runs first for a reason: if it does not fail, the plugin mechanism is
    # broken and no verdict below means anything. This driver documented that principle and did
    # not apply it, which is how its first table reported three clean kills from runs that had
    # executed no tests at all.
    ("CONTROL: focus_chain returns nothing", "mut_control_chain", "fail"),
    ("dialog: two declared widgets reordered", "mut_dialog_swap", "fail"),
    ("dialog: undeclared focusable control", "mut_dialog_stray", "fail"),
    ("progress view: undeclared focusable control", "mut_view_stray", "fail"),
    ("progress view: delivered order reversed", "mut_view_reverse", "survives"),
]


#: pytest's own exit codes. Only TESTS_FAILED means a mutation was caught: the first version of
#: this driver treated *any* non-zero code as a kill, and then forgot to pass its own environment
#: to the subprocess — so `-p <plugin>` was an unknown plugin, pytest exited 4 (usage error), and
#: four runs were reported as a clean kill table having executed no tests at all.
ALL_PASSED, TESTS_FAILED, INTERRUPTED, INTERNAL_ERROR, USAGE_ERROR, NO_TESTS = range(6)


def run(plugin):
    environment = dict(os.environ)
    environment["QT_QPA_PLATFORM"] = "windows"
    environment["PYTHONPATH"] = str(MUTATIONS)
    command = [str(PYTHON), "-m", "pytest", "-q", "-m", "windows_desktop"]
    if plugin:
        command += ["-p", plugin]
    done = subprocess.run(  # noqa: S603 - the command is built from this file's own constants
        command, cwd=ROOT, capture_output=True, text=True, env=environment
    )
    stdout = [line for line in done.stdout.splitlines() if line.strip()]
    stderr = [line for line in done.stderr.splitlines() if line.strip()]
    summary = stdout[-1] if stdout else (stderr[-1] if stderr else "(no output at all)")
    return done.returncode, summary


print(f"python : {PYTHON}")
print(f"cwd    : {ROOT}\n")

results = []
for name, plugin, expectation in CASES:
    code, summary = run(plugin)
    if code not in (ALL_PASSED, TESTS_FAILED):
        # Ran nothing, or could not. Never a verdict about the mutation.
        verdict = f"NO RESULT (exit {code})"
    elif expectation == "pass":
        verdict = "OK" if code == ALL_PASSED else "BROKEN BASELINE"
    elif expectation == "fail":
        verdict = "KILLED" if code == TESTS_FAILED else "SURVIVED (unexpected)"
    else:
        verdict = "SURVIVED (expected)" if code == ALL_PASSED else "KILLED (unexpected)"
    results.append((verdict, name, summary))
    print(f"{verdict:<22} {name}")
    print(f"{'':<22} exit {code}: {summary}\n")

print("=" * 72)
for verdict, name, _ in results:
    print(f"{verdict:<22} {name}")

unexpected = [
    r
    for r in results
    if "unexpected" in r[0] or r[0] == "BROKEN BASELINE" or r[0].startswith("NO RESULT")
]
sys.exit(1 if unexpected else 0)
