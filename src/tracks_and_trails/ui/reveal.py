"""Open a completed file, or reveal it in the file manager (`T-086`, `REQ-021`).

**The one place in Phase 2 where this application asks the operating system to act on a path.**
`T-034` governs where files may be *written*; this is the reverse direction, and it is small in code
and disproportionate in risk.

## Open and Reveal are different operations and take different routes

They were one route and that was `T086-R1`. On Windows, Open ran `explorer <path>` and a comment
claimed it launched the file's associated application. **`explorer` is the file-manager process**;
Windows' documented associated-application operations are `ShellExecuteW`'s `open` verb and
`os.startfile`, which wraps it. An argv assertion could never have caught that — it proves a list
was built, not what the operating system does with it.

So Open has a launcher seam of its own: `os.startfile` on Windows, `xdg-open` on Linux. `explorer`
stays where it belongs, on the `/select,` Reveal route.

## A path is an argument, never a command

Reveal is `explorer /select, <path>` on Windows and a file-manager call on Linux. Both take the path
as an **argv element** — `subprocess` with a list, never a string, and never `shell=True`. A title
containing a quote, a space, or a leading dash is an ordinary title (`T-034` has the fixtures) and
must not become an argument boundary. There is no shell in this module and nothing here builds a
command line by concatenation.

## The platform is a parameter, not a narrowing

Every command builder here takes `platform` with `sys.platform` as its default. That is not
indirection for its own sake: `explorer /select, <path>` is the detail in this module most likely to
be written wrongly, and with `sys.platform` read inline it could only ever be checked *on Windows* —
so a Linux-only contributor would change it blind. As a parameter, **the Windows argv is asserted by
the ordinary test suite on any machine**, and `mypy --platform win32` still typechecks both branches
instead of declaring one of them dead.

## Contained, checked at the moment of use

`REQ-021` opens files *this application downloaded*, and `is_contained` is asked again here rather
than trusted from when the path was stored. **A stored path is durable and the world is not**: the
output directory can be reconfigured, and a path is data like any other. `SEC-001`'s posture is that
the boundary is checked where it is crossed.

*(This said "a `history` row is durable". The row is gone — `T-169`/`T-170` withdrew `REQ-020` and
migration `0009` dropped the table — and the argument never depended on it: what is re-checked is a
path this application stored at some earlier moment, whichever row holds it. `T-186`.)*

## Failure is reported, never silent

A file that has been moved or deleted is the *ordinary* case here — `UX-001` says remove never
deletes a file, so the user is free to move their downloads and often will. Answering with a reason
the caller can show is the whole contract; `NFR-006` applies to this surface as much as to an
extractor's message.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Protocol

from tracks_and_trails.core.paths import is_contained

#: How long to wait for the launcher to *start*. It is not the file manager's lifetime — that
#: outlives us — only the moment between spawning and knowing whether spawning worked.
LAUNCH_TIMEOUT_SECONDS: Final = 10.0

#: The one D-Bus call that selects a file in a Linux file manager, and the tool that makes it.
DBUS_TOOL: Final = "dbus-send"


class Starter(Protocol):
    """How Windows is asked to open a file with its associated application.

    `os.startfile` satisfies it. A protocol rather than the function itself so the route can be
    asserted from Linux, where `os.startfile` does not exist.
    """

    def __call__(self, path: Path, /) -> None: ...


class Spawner(Protocol):
    """How a command is launched, injected so tests assert argv without launching anything.

    `subprocess.run` satisfies it. **The argv is the property worth testing in this module** — the
    quoting and the comma, not the spawning — and a test that actually opened a file manager on the
    machine running the suite would test the machine instead.
    """

    def __call__(self, args: list[str], /, **kwargs: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class Refusal:
    """Why nothing was opened. **A value, not an exception, and not silence.**

    A caller in a Qt slot needs something to show the user; raising out of a slot is printed and
    swallowed, which is the failure mode `NFR-006` exists to prevent one layer up.
    """

    reason: str
    #: **The file is no longer where it was recorded** (`T-346`). The one refusal a user can act on
    #: from the queue, by removing the row, so the window offers that and the others it does not.
    missing: bool = False


def _refuse_unless_usable(path: Path, within: Path) -> Refusal | None:
    """The two checks both entry points share, in the order that matters.

    **Containment first.** A path outside the output directory is refused whether or not it exists,
    so the answer never depends on what happens to be on disk — and so a probe cannot use this to
    learn that some file elsewhere exists.
    """
    if not is_contained(path, within):
        return Refusal(
            f"{path} is outside the download folder, so this application will not open it."
        )
    if not path.exists():
        return Refusal(
            f"{path.name} is no longer in {path.parent}. It may have been moved, renamed or "
            "deleted.",
            missing=True,
        )
    return None


def open_file(
    path: Path,
    *,
    within: Path,
    run: Spawner | None = None,
    start: Starter | None = None,
    platform: str = sys.platform,
) -> Refusal | None:
    """Open `path` with the application the desktop associates with it.

    `None` means it was launched. **Two routes, because the platforms genuinely differ** — Windows
    has an associated-application API and Linux has a launcher binary — and pretending otherwise is
    what `T086-R1` found: `explorer <path>` navigates the file manager, it does not open the file
    with its player.
    """
    refusal = _refuse_unless_usable(path, within)
    if refusal is not None:
        return refusal
    if platform == "win32":
        return _start_associated(path, start)
    return _spawn(open_command(path, platform), run)


def _start_associated(path: Path, start: Starter | None) -> Refusal | None:
    """The Windows Open route: `os.startfile`, which is `ShellExecuteW`'s `open` verb.

    **Injected, so the route is asserted on every platform** — that a Windows Open goes through the
    associated-application API and never builds an argv is a property this project can check from
    Linux, and `T086-R1` exists because the previous design could only be checked by opening a file
    on a desktop nobody automates.

    What this still does **not** establish is that a real Explorer session launches the right
    application; that is desktop behaviour and stays with the `STARBASE` slice.
    """
    launcher = start if start is not None else start_associated
    try:
        launcher(path)
    except OSError as error:
        # `os.startfile` raises `OSError` when no application is associated with the extension,
        # which is an ordinary configuration rather than a fault.
        return Refusal(
            f"Windows could not open {path.name} — there may be no application associated with "
            f"this kind of file. ({error})"
        )
    return None


def reveal_file(
    path: Path,
    *,
    within: Path,
    run: Spawner | None = None,
    platform: str = sys.platform,
) -> Refusal | None:
    """Show `path` in the file manager, selected. `None` means it was launched.

    **Bringing an already-open window forward is not done here** (`T347-R4`). It is a sequence of
    blocking D-Bus round trips, this runs on the GUI thread, and `NFR-001` does not allow a stalled
    file manager to freeze the application. `raise_the_file_manager` is that half, and
    `ui/file_actions.py` runs it on a worker once this has returned.
    """
    refusal = _refuse_unless_usable(path, within)
    if refusal is not None:
        return refusal
    return _spawn(reveal_command(path, platform), run)


# --- bringing an already-open window forward (`T-347`) -----------------------------------------
#
# **Measured on KDE Plasma Wayland, which is where the report came from**
# (`docs/project/evidence/2026-09-18-T347-raising-dolphin.md`). With no window showing the folder,
# `ShowItems` opens one and it arrives in front. With one already showing it, that window is reused
# and **left exactly where it was** — behind another window, or minimized on the taskbar.
#
# **Nothing in Qt can fix that.** Raising somebody else's window on Wayland needs an
# xdg-activation token from the application the user clicked in, `Dolphin.activateWindow` takes one,
# an empty one does nothing, and PySide6 exposes no way to obtain one.
#
# **So the ruling of 2026-09-18 is this narrow route**: ask KWin to activate the window, and only
# the window of the Dolphin instance that already has the folder open. Anything missing — another
# desktop, no KWin, no match — leaves the behaviour exactly as it was.


#: Dolphin publishes one bus name per instance, ending in its process id. That id is the only exact
#: link between "the instance showing this folder" and "this window", because `WindowsRunner`'s
#: matches carry an **icon name** where an application id would be useful (`T347-R1`).
DOLPHIN_PREFIX: Final = "org.kde.dolphin-"

#: KWin's own answer for what a window belongs to, read through `getWindowInfo`.
DOLPHIN_CLASS: Final = "org.kde.dolphin"

#: The query only has to *generate* candidates; the pid picks among them, so this can be broad.
WINDOW_QUERY: Final = "dolphin"

#: Where one match record *appears* to begin in `dbus-send --print-reply=literal` output.
#:
#: **A heuristic, and the second pass of `T347-R3` is right to say so.** The literal printer emits
#: strings bare, with no quoting, so a window caption containing `struct {` opens a record here as
#: surely as a real one does. Nothing that reads this format by splitting it can be exact; what
#: makes that harmless is stated on `candidate_uuids`, and it is not this line.
_RECORD = "struct {"

#: `<action>_{uuid}`, as `WindowsRunner` spells a match id, anchored to the start of a record so a
#: window **caption** cannot supply one (`T347-R3`).
_MATCH_ID = re.compile(r"^\s*(\d+)_\{([0-9a-f-]+)\}")

#: KWin's runner defines its actions in order, `ActivateAction` first and `CloseAction` second, and
#: `Run` reads the integer out of the id it is given. **So an id is not a name, it is an
#: instruction**, and the only one this application ever issues is activation.
ACTIVATE_ACTION: Final = 0

#: `dict entry( key variant value )`, as `dbus-send --print-reply=literal` prints a property map.
_PROPERTY = re.compile(r"dict entry\(\s*(\S+)\s+variant\s+(.*?)\s*\)", re.S)


def list_names_command() -> list[str]:
    """The argv that asks the session bus who is on it."""
    return [
        DBUS_TOOL,
        "--session",
        "--print-reply=literal",
        "--dest=org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus.ListNames",
    ]


def item_visible_command(name: str, path: Path) -> list[str]:
    """The argv that asks one Dolphin instance whether **this file** is shown in one of its views.

    **The file, not its folder** (`T347-R1`). Asking `isUrlOpen(folder)` says only that some tab
    has the folder open, which several instances can answer yes to at once, and the reveal went to
    exactly one of them. Dolphin's own `ShowItems` picks its recipient by walking from the active
    window and testing item visibility — not by taking the first instance in any order — so the
    nearest question this application can ask is the one Dolphin itself uses.

    It is still not proof of which instance received the call, which is why an ambiguous answer
    declines rather than guesses.
    """
    return [
        DBUS_TOOL,
        "--session",
        "--print-reply=literal",
        f"--dest={name}",
        "/dolphin/Dolphin_1",
        "org.kde.dolphin.MainWindow.isItemVisibleInAnyView",
        f"string:{path.as_uri()}",
    ]


def window_match_command() -> list[str]:
    """The argv that asks KWin for candidate windows."""
    return [
        DBUS_TOOL,
        "--session",
        "--print-reply=literal",
        "--dest=org.kde.KWin",
        "/WindowsRunner",
        "org.kde.krunner1.Match",
        f"string:{WINDOW_QUERY}",
    ]


def window_info_command(uuid: str) -> list[str]:
    """The argv that asks KWin what a window is, by its own uuid."""
    return [
        DBUS_TOOL,
        "--session",
        "--print-reply=literal",
        "--dest=org.kde.KWin",
        "/KWin",
        "org.kde.KWin.getWindowInfo",
        f"string:{uuid}",
    ]


def activate_command(uuid: str) -> list[str]:
    """The argv that asks KWin to bring the window `uuid` forward.

    **It takes the window, and builds the instruction itself** (`T347-R3`). It used to take the
    matched id and pass it to `Run` unchanged, and that id carries the *action*: KWin's runner
    reads the integer out of it, `0` activates and **`1` closes**. A window caption containing
    `1_{…}` was enough to turn this into a request to close a window, because the id was read by
    scanning the whole reply rather than the first member of a record. Nothing captured is passed
    through now: the action is this module's constant and only the uuid comes from KWin.
    """
    return [
        DBUS_TOOL,
        "--session",
        "--print-reply=literal",
        "--dest=org.kde.KWin",
        "/WindowsRunner",
        "org.kde.krunner1.Run",
        f"string:{ACTIVATE_ACTION}_{{{uuid}}}",
        "string:",
    ]


def answered_true(text: str) -> bool:
    """Whether a `dbus-send` reply is a boolean true. Anything else, including an error, is not."""
    return "error" not in text.lower() and "true" in text.lower()


def answered_false(text: str) -> bool:
    """Whether a reply is a boolean **false**, as opposed to no usable answer at all.

    The difference matters exactly once, in `instance_showing`: a silent instance is not one that
    said no, and counting it as one turned "one yes and one unknown" into a unique answer.
    """
    return "error" not in text.lower() and "false" in text.lower()


def instance_showing(path: Path, ask: Callable[[list[str]], str]) -> str | None:
    """The one Dolphin instance showing `path`, or `None` when that is not exactly one.

    **Ambiguity declines rather than guesses** (`T347-R1`). This took the first instance in sorted
    order that had the *folder* open, which answers a question nobody asked: several instances can
    have a folder open at once, the reveal went to one of them, and Dolphin chooses that one by
    walking from the active window and testing item visibility. Raising the lexically first instead
    can bring forward a window showing an entirely different current tab.

    So the question is the item, and the answer has to be unique. Two instances showing the file is
    a situation this application cannot resolve from outside, and leaving the window where it is
    beats raising the wrong one.
    """
    names = ask(list_names_command())
    showing = []
    for name in sorted(n for n in names.split() if n.startswith(DOLPHIN_PREFIX)):
        reply = ask(item_visible_command(name, path))
        if answered_true(reply):
            showing.append(name)
        elif not answered_false(reply):
            # **An instance that did not answer is not an instance that said no.** A timeout, an
            # error, or a reply this cannot read leaves uniqueness unestablished — and "one yes
            # and one unknown" was being treated as one yes, which is the ambiguity this whole
            # function exists to refuse.
            return None
    return showing[0] if len(showing) == 1 else None


def pid_of(name: str) -> int | None:
    """The process id a Dolphin bus name ends with."""
    tail = name.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else None


def candidate_uuids(reply: str) -> list[str]:
    """The window uuids in a `Match` reply, read from where each record **appears** to begin.

    **These are candidates, and the name is the whole claim** (`T347-R3`, second pass). This used
    to say ids were read as record members, which overstates what splitting untyped text can do: a
    caption carrying `struct {` opens a record that is not one, and an id-shaped string right after
    it is returned here. Reading the first member of each apparent record is still worth doing —
    it is what defeats the reviewer's original counterexample, where the forged id sat *after* the
    genuine one — but it is a narrowing, not a guarantee.

    **What makes a forged candidate harmless is downstream, and is a guarantee.** Only activation
    ids are kept, so a record asking for a close is dropped; `activate_command` builds the action
    from this module's own constant, so nothing captured is passed to KWin as an instruction; and
    `window_of` returns nothing until **KWin itself** says the uuid is a window whose
    `resourceClass` is Dolphin and whose `pid` is the instance that answered. A caption can put a
    uuid on this list. It cannot make KWin agree that it belongs to the process we asked about.
    """
    found = []
    for record in reply.split(_RECORD)[1:]:
        match = _MATCH_ID.match(record)
        if match is None:
            continue
        action, uuid = int(match.group(1)), match.group(2)
        if action == ACTIVATE_ACTION:
            found.append(uuid)
    return found


def window_of(pid: int, ask: Callable[[list[str]], str]) -> str | None:
    """The uuid of the window belonging to `pid`, by identity rather than by title text."""
    for uuid in candidate_uuids(ask(window_match_command())):
        pairs: list[tuple[str, str]] = _PROPERTY.findall(ask(window_info_command(uuid)))
        properties = dict(pairs)
        if properties.get("resourceClass", "").strip() != DOLPHIN_CLASS:
            continue
        if properties.get("pid", "").strip().split()[-1:] == [str(pid)]:
            return uuid
    return None


#: How long one D-Bus question may take before this gives up on the whole idea.
#:
#: **Not `LAUNCH_TIMEOUT_SECONDS`** (`T347-R4`). Ten seconds is the right patience for *launching*
#: a file manager, which a user is waiting for; it is the wrong patience for asking whether a
#: window exists, which a user did not ask for at all. A stalled Dolphin answering five questions
#: at ten seconds each is most of a minute of an application that has already done its job.
ASK_TIMEOUT_SECONDS: Final = 1.0


def raise_the_file_manager(
    path: Path,
    *,
    run: Spawner | None = None,
    platform: str = sys.platform,
    available: Callable[[], bool] | None = None,
) -> bool:
    """Bring the window already showing `path` forward. `True` if KWin was asked to.

    **Never call this on the GUI thread.** It is a short sequence of blocking round trips, and
    `NFR-001` is why `ui/file_actions.py` runs it on a worker (`T347-R4`).

    **Every step may simply not apply**, and none of them is an error worth telling anyone about:
    the platform is not Linux, `dbus-send` is absent, no single Dolphin instance shows the file
    (the common case, where the reveal has just opened a window that is already in front, and the
    ambiguous case, which declines), KWin is not the compositor, or no window carries that pid.
    Each answers `False` and leaves the behaviour exactly as it was.

    **`available` is a seam for the same reason `platform` is** (`T347-R5`): the tests drive this
    with a fake desktop, and asking the *running* machine whether `dbus-send` exists made them
    assert one thing on Linux and another on Windows. The Windows job failed on exactly that.
    `None` means ask this machine, which is what production wants.
    """
    tool_present = available if available is not None else dbus_available
    if platform == "win32" or not tool_present():
        return False

    def ask(command: list[str]) -> str:
        """One D-Bus question, with every failure answered as "no reply" rather than raised.

        A question this module asks nobody about: it is deciding whether a window can be brought
        forward, and a desktop that cannot answer is a desktop where the answer is no.
        """
        spawn: Spawner = run if run is not None else _run
        try:
            completed = spawn(
                command,
                shell=False,
                check=False,
                capture_output=True,
                text=True,
                timeout=ASK_TIMEOUT_SECONDS,
            )
        except OSError, subprocess.SubprocessError:
            return ""
        return str(getattr(completed, "stdout", "") or "")

    name = instance_showing(path, ask)
    if name is None:
        return False
    pid = pid_of(name)
    if pid is None:
        return False
    match_id = window_of(pid, ask)
    if match_id is None:
        return False
    ask(activate_command(match_id))
    return True


def open_command(path: Path, platform: str = sys.platform) -> list[str]:
    """The argv for opening **on the platforms that open by running something**.

    That is not Windows (`T086-R1`): Windows Open goes through `os.startfile` and builds no argv at
    all. This is the Linux route, and it is still a list for the module docstring's reason.

    The `platform` parameter is kept so a caller can pin it, but every value that is not `win32`
    answers the same way — there is no macOS branch, because `REQUIREMENTS.md` §7 defers macOS
    beyond Phase 5 and a branch for a platform nothing supports would look like support.
    """
    return ["xdg-open", str(path)]


def reveal_command(path: Path, platform: str = sys.platform) -> list[str]:
    """The argv for revealing, which is the platform-specific half.

    **`/select,` and the path are two arguments** — and this said the opposite until the maintainer
    found *Show in folder* opening Documents on Windows (2026-09-13). Measured on `STARBASE` with a
    file whose folder and name hold spaces, brackets and CJK text:

    | argv | Explorer did |
    |---|---|
    | `["explorer", "/select,<path>"]` (what this was) | opened **Documents**, selected nothing |
    | `explorer /select,"<path>"` as one string | opened the folder, selected nothing |
    | `["explorer", "/select,", "<path>"]` | opened the folder, **selected the file** |

    The first fails because `subprocess` renders a list for `CreateProcess` with `list2cmdline`,
    which quotes an element containing a space *whole* (`"/select,C:/My Videos/clip.mp4"`, in
    backslashes), and Explorer does not recognise a quoted switch. As its own element the path is
    quoted alone, which Explorer reads. Every form exited 1, which is why `_spawn` does not read
    Explorer's exit code.

    On Linux the D-Bus `FileManager1` interface is what selects a file, and `dbus-send` is the call
    that needs no new dependency. **When it is absent the parent directory is opened instead** —
    which selects nothing, and is the honest degradation rather than a failure: the user asked to
    find their file, and the folder holding it answers most of that.
    """
    if platform == "win32":
        return ["explorer", "/select,", str(path)]
    if not dbus_available():
        return ["xdg-open", str(path.parent)]
    return [
        DBUS_TOOL,
        "--session",
        "--dest=org.freedesktop.FileManager1",
        "--type=method_call",
        "/org/freedesktop/FileManager1",
        "org.freedesktop.FileManager1.ShowItems",
        # `as_uri()` percent-encodes, which is what makes a path with a space or a quote survive
        # the trip through D-Bus intact.
        f"array:string:{path.as_uri()}",
        "string:",
    ]


def dbus_available() -> bool:
    """Whether `dbus-send` is on `PATH`. A named seam so a test can pin either answer."""
    return shutil.which(DBUS_TOOL) is not None


def start_associated(path: Path) -> None:
    """Open `path` with its associated application: `ShellExecuteW`'s `open` verb (`T086-R1`).

    **One definition, not a module-level platform split**, and that is a deliberate trade. The split
    is this project's usual idiom (`core/instance_lock.py`) and buys per-platform type checking —
    but it also makes the Windows body *invisible to Linux*, so a mutation deleting the call
    survives every run except the Windows job. Looking the launcher up at call time means the seam
    can be verified wherever the suite runs, which is the whole lesson of this finding: the previous
    implementation was wrong precisely because nothing off Windows could see it.

    `os.startfile` exists only on Windows, so absence is the ordinary case elsewhere and **raises**
    rather than passing quietly. `open_file` routes here only when the platform is `win32`; a
    launcher that silently succeeded without launching is the failure this module is written
    against.
    """
    launcher = getattr(os, "startfile", None)
    if launcher is None:
        raise OSError(f"os.startfile is Windows-only; {path} cannot be opened by this route")
    # `ruff`'s `S606` — *starting a process without a shell* — is the property being asked for
    # rather than a risk being taken. `path` has already passed containment, and no shell is what
    # keeps a quoted or dash-leading filename an argument.
    launcher(path)


def _run(args: list[str], /, **kwargs: Any) -> Any:
    """The default `Spawner`. **The only call to `subprocess` in this package.**

    Named rather than passing `subprocess.run` itself: its typeshed signature is a set of overloads
    that does not reduce to one callable shape, and more usefully, this is the single line to read
    when asking whether a shell is ever involved.

    **`shell=True` is refused here rather than merely not passed.** `ruff`'s `S603` fires on this
    call because `kwargs` is opaque to it, and the honest answer to that warning is an enforced
    invariant instead of a suppressing comment: `args` is a list this module built, and a caller
    that asked for a shell gets an error rather than a shell.
    """
    if kwargs.get("shell"):
        raise ValueError("this module never runs a command through a shell")
    kwargs["shell"] = False
    return subprocess.run(args, **kwargs)  # noqa: S603 - `shell` is pinned False on the line above


def _spawn(command: list[str], run: Spawner | None) -> Refusal | None:
    """Launch `command`, reporting a failure rather than raising into a Qt slot.

    **`shell=False`, which is `subprocess`'s default and is stated anyway**, because the one thing
    this module must never do is the thing a future edit would add without noticing.

    A non-zero exit is reported: `xdg-open` returns 2 for a malformed argument and 3 when no
    application is configured, and a user with no file manager installed deserves to be told that
    rather than to watch nothing happen.
    """
    spawn: Spawner = run if run is not None else _run
    try:
        completed = spawn(
            command,
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            timeout=LAUNCH_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return Refusal(
            f"{command[0]} is not installed, so this application cannot ask your desktop to open "
            "the file."
        )
    except subprocess.TimeoutExpired:
        return Refusal(f"{command[0]} did not respond, so nothing was opened.")
    except OSError as error:
        return Refusal(f"Could not ask your desktop to open the file: {error}")

    code = getattr(completed, "returncode", 0)
    # **Explorer's exit code means nothing** (measured, `reveal_command`): it returned 1 for a
    # reveal that opened the folder and selected the file, and for one that failed, alike.
    if code and command[0] != "explorer":
        detail = (getattr(completed, "stderr", "") or "").strip()
        return Refusal(
            f"Your file manager reported an error (exit {code})." + (f" {detail}" if detail else "")
        )
    return None
