"""Run T-026's mutation classes against the windows_desktop suite, on a real Windows desktop.

`T-040` has required this since it was filed and it has never run anywhere: the GitHub job proves
the tests pass, which is not evidence about a mutation nobody executed.

MUST be run from the RDP/console session. Over SSH there is no window station, so Qt cannot
create a window and every result would be meaningless rather than merely wrong.

Each mutation is a pytest plugin, so the checkout is never modified and a crash cannot leave a
half-mutated file behind. Run it from the repository root.
"""

import os
import re
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

#: `T-026`'s classes run the desktop-marked suite on the real plugin, because that is what they
#: are about: window stations, focus chains and native widgets.
DESKTOP = (["-m", "windows_desktop"], "windows")

#: `T-329`'s class runs the rendered-focus sweep **offscreen**, and that is not a shortcut.
#: `docs/project/TESTING.md` §2 runs the UI suite headless and the `frozen`/`windows desktop`
#: full-suite step sets `QT_QPA_PLATFORM=offscreen` — so offscreen is the configuration in which
#: this gate actually guards the product on this machine, and a mutation proving it in some other
#: configuration would be proving it somewhere nobody runs it.
FOCUS = (
    [
        "tests/ui/test_colour_is_never_alone.py::"
        "test_focus_is_visible_on_every_control_the_application_shows"
    ],
    "offscreen",
)

#: The suite that detects an emptied focus chain. `T-331`: the desktop suite does not, because
#: it writes its expected order out by hand and construction order already matches.
CHAIN = (["tests/ui/test_accessibility.py", "tests/ui/test_add_dialog.py"], "offscreen")

CASES = [
    ("baseline, unmutated", None, "pass", DESKTOP),
    # The positive control runs first for a reason: if it does not fail, the plugin mechanism is
    # broken and no verdict below means anything. This driver documented that principle and did
    # not apply it, which is how its first table reported three clean kills from runs that had
    # executed no tests at all.
    #
    # **It is the title control since `T-331`.** The previous one emptied the dialog's focus
    # chain, and that can survive for a product reason — construction order already matches the
    # declaration — which is the one thing a control must never do. This one changes the window
    # title, and the desktop suite asks *Windows* for it through `GetWindowTextW` rather than
    # asking Qt, so no arrangement of widgets can pass it.
    ("CONTROL: the window title is wrong", "mut_control_title", "fail", DESKTOP),
    ("dialog: two declared widgets reordered", "mut_dialog_swap", "fail", DESKTOP),
    ("dialog: undeclared focusable control", "mut_dialog_stray", "fail", DESKTOP),
    ("progress view: undeclared focusable control", "mut_view_stray", "fail", DESKTOP),
    ("progress view: delivered order reversed", "mut_view_reverse", "survives", DESKTOP),
    # `T-331`. Run against the suite that detects it rather than the one that cannot.
    ("baseline: the chain suite, unmutated", None, "pass", CHAIN),
    ("dialog: the declared chain is emptied", "mut_control_chain", "fail", CHAIN),
    # `T329-R2`. Its own baseline is here rather than borrowed from the one above: a different
    # selection and a different platform plugin is a different run, and an unmutated pass is the
    # only thing that makes the line under it mean anything.
    ("baseline: the rendered focus sweep, unmutated", None, "pass", FOCUS),
    ("header: draws no focus ring of its own", "mut_header_no_extra_ring", "fail", FOCUS),
]


#: pytest's own exit codes. Only TESTS_FAILED means a mutation was caught: the first version of
#: this driver treated *any* non-zero code as a kill, and then forgot to pass its own environment
#: to the subprocess — so `-p <plugin>` was an unknown plugin, pytest exited 4 (usage error), and
#: four runs were reported as a clean kill table having executed no tests at all.
ALL_PASSED, TESTS_FAILED, INTERRUPTED, INTERNAL_ERROR, USAGE_ERROR, NO_TESTS = range(6)

#: pytest's own result line. Its absence is a fact worth reporting rather than papering over.
RESULT_LINE = re.compile(r"\b\d+ (passed|failed|error|skipped)\b")


def run(plugin, selection):
    select, platform = selection
    environment = dict(os.environ)
    environment["QT_QPA_PLATFORM"] = platform
    environment["PYTHONPATH"] = str(MUTATIONS)
    command = [str(PYTHON), "-m", "pytest", "-q", *select]
    if plugin:
        command += ["-p", plugin]
    done = subprocess.run(  # noqa: S603 - the command is built from this file's own constants
        command, cwd=ROOT, capture_output=True, text=True, env=environment
    )
    stdout = [line for line in done.stdout.splitlines() if line.strip()]
    stderr = [line for line in done.stderr.splitlines() if line.strip()]
    # **pytest's result line, not merely the last one** (`T-331`). Taking `stdout[-1]` returned
    # the progress dots on a run whose summary never arrived, so every case in that table read
    # `exit 1: ..............` and the verdicts built on it were unreadable.
    result = next(
        (line for line in reversed(stdout) if RESULT_LINE.search(line)),
        None,
    )
    summary = result or (stdout[-1] if stdout else stderr[-1] if stderr else "(no output at all)")
    if result is None:
        summary = f"NO SUMMARY LINE — last output was: {summary}"
    return done.returncode, summary, done.stdout + done.stderr


def describe_the_tree():
    """What is actually being tested — `T-331`, and the reason this exists is worth keeping.

    This driver already refuses the wrong interpreter and the wrong directory. On 2026-09-11 it
    printed a full table from a checkout that was **six weeks stale** — its `origin` was a local
    bundle file, so every `git pull` answered *"Already up to date"* — with uncommitted edits to
    `core/logging.py` on top. Three runs were spent before anyone asked what `git log` said.

    A mutation table is a claim about a tree. A table that does not name its tree is not evidence.
    """

    def git(*arguments):
        try:
            # `S603`/`S607`: fixed arguments, no shell, no user input. `git` is resolved from
            # PATH deliberately — this has to work from a console on a machine whose git is
            # wherever its installer put it.
            done = subprocess.run(  # noqa: S603
                ["git", *arguments],  # noqa: S607
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return ""
        return done.stdout.strip() if done.returncode == 0 else ""

    return git("log", "--oneline", "-1"), git("status", "--porcelain")


HEAD, DIRTY = describe_the_tree()
ALLOW_DIRTY = "--allow-dirty" in sys.argv

lines = [
    f"python : {PYTHON}",
    f"cwd    : {ROOT}",
    f"HEAD   : {HEAD or '(not a git checkout — this table names no tree)'}",
    f"tree   : {'DIRTY' if DIRTY else 'clean'}",
]
if DIRTY:
    lines += ["", "uncommitted:"] + [f"  {line}" for line in DIRTY.splitlines()]
report = list(lines)
print("\n".join(lines) + "\n")

if DIRTY and not ALLOW_DIRTY:
    # **Refuses rather than warns**, because a warning is what scrolled past on 2026-09-11.
    print(
        "refusing to run: the working tree has uncommitted changes, so no verdict below would\n"
        "name a tree anybody can return to. Commit, stash, or pass --allow-dirty if you mean it."
    )
    sys.exit(2)

results = []
broken = set()
for name, plugin, expectation, selection in CASES:
    code, summary, full = run(plugin, selection)
    key = tuple(selection[0])
    if code not in (ALL_PASSED, TESTS_FAILED):
        # Ran nothing, or could not. Never a verdict about the mutation.
        verdict = f"NO RESULT (exit {code})"
    elif expectation == "pass":
        verdict = "OK" if code == ALL_PASSED else "BROKEN BASELINE"
        if code != ALL_PASSED:
            broken.add(key)
    elif key in broken:
        # **The baseline for this selection failed, so nothing here is a verdict** (`T-331`).
        # Without this the second run of 2026-09-11 reported KILLED for every case — including
        # the one expected to survive — because the suite was failing whatever the plugin did.
        verdict = "NO RESULT (baseline broken)"
    elif expectation == "fail":
        verdict = "KILLED" if code == TESTS_FAILED else "SURVIVED (unexpected)"
    else:
        verdict = "SURVIVED (expected)" if code == ALL_PASSED else "KILLED (unexpected)"
    results.append((verdict, name, summary, full))
    block = f"{verdict:<22} {name}\n{'':<22} exit {code}: {summary}"
    report.append("\n" + block)
    print(block + "\n")

print("=" * 72)
report.append("\n" + "=" * 72)
for verdict, name, _summary, _full in results:
    print(f"{verdict:<22} {name}")
    report.append(f"{verdict:<22} {name}")

# **Written, not only printed** (`T-331`). `T329-R2` asks for a *recorded* result, and this
# driver's own table nearly went unrecorded because it lived in a console window.
RECORD = ROOT / "reports" / "windows-mutations.txt"
RECORD.parent.mkdir(parents=True, exist_ok=True)
RECORD.write_text(
    "\n".join(report)
    + "\n\n"
    + "\n\n".join(f"{'=' * 72}\n{name}\n{'=' * 72}\n{full}" for _, name, _, full in results),
    encoding="utf-8",
)
print(f"\nrecorded: {RECORD}")

unexpected = [
    r
    for r in results
    if "unexpected" in r[0] or r[0] == "BROKEN BASELINE" or r[0].startswith("NO RESULT")
]
sys.exit(1 if unexpected else 0)
