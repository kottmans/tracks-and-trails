"""Does *Show in folder* bring Dolphin to the front? The three cases, before and after (`T-347`).

`T347-R2` asked for this: a retained, runnable probe and a three-case record, rather than a
description of one case. It needs KDE Plasma on Wayland with Dolphin, which is the desktop the
report came from and no runner has.

    PYTHONPATH=tools python -m dolphin_raise_probe                 # today's behaviour
    PYTHONPATH=tools python -m dolphin_raise_probe --raise-route windowsrunner

**The instruments, and what each can and cannot say.**

- `org.kde.dolphin.MainWindow.isActiveWindow` — whether that window is the active one. It does
  **not** distinguish a window that is merely behind another from one that is minimized.
- `isUrlOpen(folder)` — whether the window is showing the folder. It does **not** assert that the
  file is selected.
- `isItemVisibleInAnyView(file)` — whether the item is shown in one of its views. Closer to what
  `ShowItems` promises, and still not the same as *highlighted*.
- `org.kde.KWin.getWindowInfo(uuid)` — `minimized`, and the identity the other three lack:
  `pid`, `resourceClass`, `desktopFile`. **The `pid` is what ties a KWin window to the Dolphin
  instance that answered `isUrlOpen`**, which is the only exact link available here.

**`WindowsRunner`'s third match member is `iconName`, not an application id** (`T347-R1`): its
signature is `a(sssuda{sv})` and KWin fills that member from the window's icon. It reads
`org.kde.dolphin` because KDE names icons after desktop ids, and an icon is not identity. This
probe never filters on it.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

from tracks_and_trails.ui.reveal import raise_the_file_manager, reveal_file

DOLPHIN_PREFIX = "org.kde.dolphin-"
#: KWin's own window identity, read through `getWindowInfo` rather than guessed from a match string.
DOLPHIN_CLASS = "org.kde.dolphin"


def dbus(*arguments: str) -> str:
    result = subprocess.run(  # noqa: S603 - `shell` stays False, so argv is argv
        # `S607`: the session's own `dbus-send`, which is how every other caller here reaches the
        # bus. A probe that hard-coded a path would measure a different machine than the one it runs
        # on.
        ["dbus-send", "--session", "--print-reply=literal", *arguments],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return (result.stdout or result.stderr).strip()


def truthy(answer: str) -> bool:
    return "true" in answer.lower()


def instances() -> list[str]:
    """Every Dolphin bus name that has a main window. `--daemon` has none and is skipped."""
    names = dbus(
        "--dest=org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus.ListNames"
    )
    found = []
    for name in sorted(n for n in names.split() if n.startswith(DOLPHIN_PREFIX)):
        if "Error" not in dbus(
            f"--dest={name}", "/dolphin/Dolphin_1", "org.kde.dolphin.MainWindow.isActiveWindow"
        ):
            found.append(name)
    return found


def ask(name: str, method: str, *arguments: str) -> str:
    return dbus(
        f"--dest={name}", "/dolphin/Dolphin_1", f"org.kde.dolphin.MainWindow.{method}", *arguments
    )


def window_info(uuid: str) -> dict[str, str]:
    """`getWindowInfo`, as the few fields this probe reads."""
    text = dbus("--dest=org.kde.KWin", "/KWin", "org.kde.KWin.getWindowInfo", f"string:{uuid}")
    pairs = dict(re.findall(r"dict entry\(\s*(\S+)\s+variant\s+(.*?)\s*\)", text, re.S))
    return {key: value.strip() for key, value in pairs.items()}


def kwin_window_for(pid: int) -> tuple[str, dict[str, str]] | None:
    """The KWin match id and info for the window of `pid`, found by identity rather than by text.

    The query only has to *generate candidates*; `pid` is what picks the right one, so a window
    whose title happens to read alike cannot be chosen by mistake.
    """
    matched = dbus(
        "--dest=org.kde.KWin", "/WindowsRunner", "org.kde.krunner1.Match", "string:dolphin"
    )
    for identifier in re.findall(r"\b(\d+_\{[0-9a-f-]+\})", matched):
        uuid = identifier.split("_", 1)[1]
        info = window_info(uuid)
        if info.get("resourceClass") != DOLPHIN_CLASS:
            continue
        if info.get("pid", "").split()[-1] == str(pid):
            return identifier, info
    return None


def state(name: str, folder: Path, target: Path) -> dict[str, Any]:
    """Everything the four instruments can say about one Dolphin window."""
    pid = int(name.rsplit("-", 1)[-1])
    found = kwin_window_for(pid)
    info = found[1] if found else {}
    return {
        "pid": pid,
        "active": truthy(ask(name, "isActiveWindow")),
        "shows the folder": truthy(ask(name, "isUrlOpen", f"string:{folder.as_uri()}")),
        "item visible": truthy(ask(name, "isItemVisibleInAnyView", f"string:{target.as_uri()}")),
        "minimized": info.get("minimized", "unknown").split()[-1],
    }


def survey(folder: Path, target: Path) -> dict[str, dict[str, Any]]:
    return {name: state(name, folder, target) for name in instances()}


def show(label: str, taken: dict[str, dict[str, Any]]) -> None:
    print(f"    {label}")
    if not taken:
        print("      (no Dolphin window)")
    for name, fields in taken.items():
        print(f"      {name}: {fields}")


def precondition(case: str, target: str | None, before: dict[str, dict[str, Any]]) -> str:
    """Whether the case this run claims to be measuring is the case it set up.

    **It asks about `target`, the window this probe opened for the case**, not about whatever the
    session happens to hold (`T347-R2`). Asking the room rather than the subject let case 4 accept a
    *different* window being minimized, and let case 3 accept a target that was minimized — so the
    two cases the whole task turns on were not distinguishable from this record.

    A case whose precondition is not established measures nothing, and says so here rather than in
    a table somebody reads later.
    """
    if case.startswith("1"):
        if before:
            return f"NOT established: {sorted(before)} is still open"
        return "established: no Dolphin window at all"

    if target is None:
        return "NOT established: this probe opened no window for the case"
    if target not in before:
        return f"NOT established: {target} is gone"
    state = before[target]

    if case.startswith("2"):
        showing = [name for name, fields in before.items() if fields["shows the folder"]]
        if showing:
            return f"NOT established: {showing} already shows the folder"
        return f"established: {target} is open and no window shows the folder"

    if not state["shows the folder"]:
        return f"NOT established: {target} does not show the folder"
    if state["active"]:
        return f"NOT established: {target} is already active, so nothing has to be raised"

    if case.startswith("3"):
        if state["minimized"] == "true":
            return f"NOT established: {target} is minimized, which is case 4 and not this one"
        return f"established: {target} shows the folder, is behind ours and is not minimized"

    if state["minimized"] != "true":
        return f"NOT established: {target} is not minimized, which is case 3 and not this one"
    return f"established: {target} shows the folder and is minimized"


def pid_of(name: str) -> int:
    """The process id a Dolphin bus name ends with."""
    return int(name.rsplit("-", 1)[-1])


def minimized_now(name: str, folder: Path, target: Path) -> bool:
    """Whether KWin reports `name`'s window minimized, asked until it agrees."""
    return state(name, folder, target)["minimized"] == "true"


def show_items(target: Path) -> None:
    """Exactly what the application sends today."""
    subprocess.run(  # noqa: S603 - `shell` stays False
        [  # noqa: S607 - the session's own `dbus-send`, as `dbus()` above records
            "dbus-send",
            "--session",
            "--dest=org.freedesktop.FileManager1",
            "--type=method_call",
            "/org/freedesktop/FileManager1",
            "org.freedesktop.FileManager1.ShowItems",
            f"array:string:{target.as_uri()}",
            "string:",
        ],
        check=False,
        capture_output=True,
    )


def raise_through_windowsrunner(folder: Path) -> str:
    """The proposed route: find the window of the instance showing `folder`, by pid, and run it."""
    showing = [
        name for name in instances() if truthy(ask(name, "isUrlOpen", f"string:{folder.as_uri()}"))
    ]
    if not showing:
        return "no Dolphin window shows that folder"
    pid = int(showing[0].rsplit("-", 1)[-1])
    found = kwin_window_for(pid)
    if found is None:
        return f"no KWin window carries pid {pid}"
    answer = dbus(
        "--dest=org.kde.KWin",
        "/WindowsRunner",
        "org.kde.krunner1.Run",
        f"string:{found[0]}",
        "string:",
    )
    return f"ran {found[0]}" if "Error" not in answer else f"error: {answer.splitlines()[0][:60]}"


def steal_focus() -> subprocess.Popen[bytes]:
    """A window this probe owns, so Dolphin is demonstrably behind something."""
    code = (
        "from PySide6.QtWidgets import QApplication, QLabel;"
        "from PySide6.QtCore import QTimer;"
        "app = QApplication([]);"
        "w = QLabel('T-347 probe window'); w.setWindowTitle('T-347 probe'); w.resize(460, 110);"
        "w.show(); w.raise_(); w.activateWindow();"
        "QTimer.singleShot(300000, app.quit); app.exec()"
    )
    return subprocess.Popen([sys.executable, "-c", code])  # noqa: S603 - this interpreter


#: KWin's scripting API is the only way this probe can minimize a window: nothing on Dolphin's own
#: interface does it, and a Wayland client cannot minimize somebody else's window.
#: Minimizes **only the listed process ids**, so a window the operator owns is never touched
#: (`T347-R2`). The first version minimized every Dolphin window while its own message said
#: otherwise.
MINIMIZE_SCRIPT = """
const wanted = [%s];
for (const w of workspace.windowList()) {
    if (wanted.includes(w.pid) && !w.minimized) {
        w.minimized = true;
    }
}
"""


def minimize(pids: list[int], settled: Callable[[], bool]) -> str:
    """Minimize the windows of `pids`, and **wait until KWin says it happened** before unloading.

    **The wait is the whole point** (`T347-R2`). Unloading the script immediately after `run`
    reported success while leaving every window un-minimized: the script is torn down before KWin
    applies it. `settled` is asked until it agrees, so the case that follows is measuring the state
    it says it is.
    """
    folder = Path(tempfile.mkdtemp(prefix="t347-minimize-"))
    script = folder / "minimize.js"
    script.write_text(MINIMIZE_SCRIPT % ", ".join(str(pid) for pid in pids), encoding="utf-8")
    loaded = dbus(
        "--dest=org.kde.KWin",
        "/Scripting",
        "org.kde.kwin.Scripting.loadScript",
        f"string:{script}",
        "string:t347minimize",
    )
    if "Error" in loaded:
        return f"could not load the script: {loaded.splitlines()[0][:60]}"
    number = loaded.strip().split()[-1]
    ran = dbus("--dest=org.kde.KWin", f"/Scripting/Script{number}", "org.kde.kwin.Script.run")
    if "Error" in ran:
        return f"run failed: {ran.splitlines()[0][:60]}"

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if settled():
            dbus(
                "--dest=org.kde.KWin",
                "/Scripting",
                "org.kde.kwin.Scripting.unloadScript",
                "string:t347minimize",
            )
            return "minimized, and KWin agrees"
        time.sleep(0.5)
    dbus(
        "--dest=org.kde.KWin",
        "/Scripting",
        "org.kde.kwin.Scripting.unloadScript",
        "string:t347minimize",
    )
    return "NOT minimized: KWin never reported it"


#: The Dolphin processes this probe started, so it never closes a window the operator owns.
STARTED: list[subprocess.Popen[bytes]] = []

#: Every Dolphin window that existed before this run. Anything not here appeared **because of**
#: this probe — the windows `ShowItems` itself spawns included. The first version tracked only what
#: it launched, so a spawned window stayed open and the next case found the folder already
#: showing and could not establish itself.
PRE_EXISTING: set[str] = set()


def open_dolphin_on(folder: Path) -> str | None:
    """A Dolphin window showing `folder` in a **clean profile**, named so a case can ask about it.

    **`XDG_CONFIG_HOME` is redirected per run**, and that is load-bearing rather than tidy:
    Dolphin restores its previous tabs, so a window opened "somewhere else" still had the target
    folder open in another tab, and `isUrlOpen` answered **true** before the reveal. Case 2 was not
    case 2. Measured both ways — with the operator's profile the answer is true, with a fresh one
    it is false.
    """
    environment = dict(os.environ, XDG_CONFIG_HOME=tempfile.mkdtemp(prefix="t347-profile-"))
    started = subprocess.Popen(  # noqa: S603 - `shell` stays False
        ["dolphin", "--new-window", str(folder)],  # noqa: S607 - the session's own Dolphin
        env=environment,
    )
    STARTED.append(started)
    time.sleep(5)
    for name in instances():
        if pid_of(name) == started.pid:
            return name
    return None


def quit_dolphins() -> None:
    """Close every window this run caused, and nothing that was there before it."""
    for name in instances():
        if name not in PRE_EXISTING:
            ask(name, "quit")
    STARTED.clear()
    time.sleep(2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folder", type=Path, required=True, help="a folder holding one file")
    parser.add_argument(
        "--raise-route",
        choices=("none", "windowsrunner", "production"),
        default="none",
        help=(
            "none: ShowItems alone, the behaviour before T-347. windowsrunner: this tool's own "
            "activation. production: the application's own reveal_file and raise_the_file_manager, "
            "which is the only route that measures what ships"
        ),
    )
    arguments = parser.parse_args()

    PRE_EXISTING.update(instances())
    if PRE_EXISTING:
        print(f"already open, and left alone: {sorted(PRE_EXISTING)}")
        print("case 1 needs no Dolphin window at all, so it cannot establish itself here.\n")

    folder = arguments.folder.resolve()
    files = [p for p in folder.iterdir() if p.is_file()]
    if not files:
        print(f"{folder} holds no file to reveal")
        return 1
    target = files[0]
    print(f"folder: {folder}")
    print(f"target: {target.name}")
    print(f"route after ShowItems: {arguments.raise_route}\n")

    # **Not `folder.parent`**, which the first version used: `isUrlOpen(target folder)` answered
    # true for a window showing the parent, so "open on another folder" was not another folder and
    # the case proved nothing. An unrelated directory is what makes case 2 that case.
    elsewhere = Path(tempfile.mkdtemp(prefix="t347-elsewhere-"))
    thief: subprocess.Popen[bytes] | None = None
    try:
        for case, where, minimize_it in (
            ("1. nothing open", None, False),
            ("2. open on another folder", elsewhere, False),
            ("3. open on the target folder", folder, False),
            ("4. open on the target folder, minimized", folder, True),
        ):
            print(f"  == {case} ==")
            quit_dolphins()
            opened = None
            if where is not None:
                opened = open_dolphin_on(where)
            if minimize_it and opened is not None:
                # `opened` is bound here rather than captured, so the closure cannot read a later
                # iteration's window (`B023`).
                its_name = opened
                settled = partial(minimized_now, its_name, folder, target)
                print(f"    {minimize([pid_of(its_name)], settled)}")
            if thief is not None:
                thief.terminate()
            thief = steal_focus()
            time.sleep(3)
            before = survey(folder, target)
            show("before", before)
            print(f"    precondition: {precondition(case, opened, before)}")

            if arguments.raise_route == "production":
                # **The application's own functions**, which is the only way this tool measures
                # what ships rather than its own copy of the idea (`T347-R2`).
                print(f"    reveal_file -> {reveal_file(target, within=folder, platform='linux')}")
                time.sleep(3)
                print(f"    raise_the_file_manager -> {raise_the_file_manager(target)}")
            else:
                show_items(target)
                time.sleep(4)
                if arguments.raise_route == "windowsrunner":
                    print(f"    route: {raise_through_windowsrunner(folder)}")
            time.sleep(3)
            show("after", survey(folder, target))
            print()
    finally:
        if thief is not None:
            thief.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
