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
    # **What the control proves, and what it does not** (`T331-R2`). It shows the plugin
    # mechanism takes effect on this machine: a mutation no product arrangement can pass is
    # caught. If it survived, that would say the mechanism is suspect and the table must be read
    # with care — it would **not** void a later kill, because each kill carries its own evidence:
    # a baseline that passed and a run with real assertion failures. *(This said a surviving
    # control made every verdict below meaningless, which the 2026-09-11 run disproved.)*
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
    # **"fail", not "survives"**, since `T-084` gave the failed state a third control; see the
    # mutation's docstring for the 2026-09-13 run that showed it.
    ("progress view: delivered order reversed", "mut_view_reverse", "fail", DESKTOP),
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
RESULT_LINE = re.compile(r"\b\d+ (passed|failed|errors?|skipped|deselected)\b")


def counts(summary):
    """`{"passed": n, "failed": n, "errors": n}` from pytest's result line; zeros when absent."""
    found = {"passed": 0, "failed": 0, "errors": 0}
    for number, word in re.findall(r"\b(\d+) (passed|failed|errors?)\b", summary or ""):
        found["errors" if word.startswith("error") else word] += int(number)
    return found


def verdict(expectation, code, summary, baseline_broken):
    """The table's word for one run — and **nothing is a kill without an assertion failing**.

    `T331-R1`: this awarded KILLED to any exit 1, so a run with only errors — a fixture that could
    not build, a collection that half-failed — or with no result line at all read as a caught
    mutation, and a baseline exiting 2 to 5 was never marked broken, so its mutations were judged
    against nothing. Now:

    - a **baseline** is OK only on exit 0 with tests passed and none failed or errored; anything
      else marks its selection broken, whatever the exit code;
    - a **kill** needs exit 1 *and* at least one failed test — teardown errors beside real
      failures are kept, as the Windows runs showed they cascade — and anything else from exit 1
      is `NO RESULT (errors only)` or `NO RESULT (no summary)`;
    - a **survivor** needs exit 0 with tests passed; every other exit is `NO RESULT`.
    """
    seen = counts(summary)
    has_summary = RESULT_LINE.search(summary or "") is not None and "NO SUMMARY LINE" not in (
        summary or ""
    )
    if expectation == "pass":
        clean = code == ALL_PASSED and has_summary and seen["passed"] > 0
        clean = clean and seen["failed"] == 0 and seen["errors"] == 0
        if clean:
            return "OK"
        return (
            "BROKEN BASELINE" if code in (ALL_PASSED, TESTS_FAILED) else f"NO RESULT (exit {code})"
        )
    if baseline_broken:
        return "NO RESULT (baseline broken)"
    if code == TESTS_FAILED:
        if not has_summary:
            return "NO RESULT (no summary)"
        if seen["failed"] == 0:
            return "NO RESULT (errors only)"
        return "KILLED" if expectation == "fail" else "KILLED (unexpected)"
    if code == ALL_PASSED and has_summary and seen["passed"] > 0 and seen["errors"] == 0:
        return "SURVIVED (unexpected)" if expectation == "fail" else "SURVIVED (expected)"
    return f"NO RESULT (exit {code})"


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


def main():
    if not (ROOT / "pyproject.toml").is_file():
        raise SystemExit(f"run this from the repository root; {ROOT} has no pyproject.toml")
    if ".venv" not in str(PYTHON):
        raise SystemExit(f"run this with the project venv's python, not {PYTHON}")

    head, dirty = describe_the_tree()
    allow_dirty = "--allow-dirty" in sys.argv

    lines = [
        f"python : {PYTHON}",
        f"cwd    : {ROOT}",
        f"HEAD   : {head or '(not a git checkout — this table names no tree)'}",
        f"tree   : {'dirty' if dirty else 'clean'}",
    ]
    if dirty:
        lines += ["", "uncommitted:"] + [f"  {line}" for line in dirty.splitlines()]
    report = list(lines)
    print("\n".join(lines) + "\n")

    if dirty and not allow_dirty:
        # **Refuses rather than warns**, because a warning is what scrolled past on 2026-09-11.
        print(
            "refusing to run: the working tree has uncommitted changes, so no verdict below\n"
            "would name a tree anybody can return to. Commit, stash, or pass --allow-dirty\n"
            "if you mean it."
        )
        sys.exit(2)

    results = []
    broken = set()
    for name, plugin, expectation, selection in CASES:
        code, summary, full = run(plugin, selection)
        key = tuple(selection[0])
        # **A baseline that is not clean breaks its selection, whatever its exit code**
        # (`T331-R1`).
        # Without this the second run of 2026-09-11 reported KILLED for every case — including the
        # one expected to survive — because the suite was failing whatever the plugin did.
        word = verdict(expectation, code, summary, key in broken)
        if expectation == "pass" and word != "OK":
            broken.add(key)
        results.append((word, name, summary, full))
        block = f"{word:<22} {name}\n{'':<22} exit {code}: {summary}"
        report.append("\n" + block)
        print(block + "\n")

    print("=" * 72)
    report.append("\n" + "=" * 72)
    for word, name, _summary, _full in results:
        print(f"{word:<22} {name}")
        report.append(f"{word:<22} {name}")

    # **Written, not only printed** (`T-331`). `T329-R2` asks for a *recorded* result, and this
    # driver's own table nearly went unrecorded because it lived in a console window.
    record = ROOT / "reports" / "windows-mutations.txt"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(
        "\n".join(report)
        + "\n\n"
        + "\n\n".join(f"{'=' * 72}\n{name}\n{'=' * 72}\n{full}" for _, name, _, full in results),
        encoding="utf-8",
    )
    print(f"\nrecorded: {record}")

    unexpected = [
        r
        for r in results
        if "unexpected" in r[0] or r[0] == "BROKEN BASELINE" or r[0].startswith("NO RESULT")
    ]
    sys.exit(1 if unexpected else 0)


if __name__ == "__main__":
    main()
