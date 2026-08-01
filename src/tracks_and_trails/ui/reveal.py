"""Open a completed file, or reveal it in the file manager (`T-086`, `REQ-021`).

**The one place in Phase 2 where this application asks the operating system to act on a path.**
`T-034` governs where files may be *written*; this is the reverse direction, and it is small in code
and disproportionate in risk.

## A path is an argument, never a command

Reveal is `explorer /select,<path>` on Windows and a file-manager call on Linux. Both take the path
as an **argv element** — `subprocess` with a list, never a string, and never `shell=True`. A title
containing a quote, a space, or a leading dash is an ordinary title (`T-034` has the fixtures) and
must not become an argument boundary. There is no shell in this module and nothing here builds a
command line by concatenation.

## The platform is a parameter, not a narrowing

Every command builder here takes `platform` with `sys.platform` as its default. That is not
indirection for its own sake: `explorer /select,<path>` is the detail in this module most likely to
be written wrongly, and with `sys.platform` read inline it could only ever be checked *on Windows* —
so a Linux-only contributor would change it blind. As a parameter, **the Windows argv is asserted by
the ordinary test suite on any machine**, and `mypy --platform win32` still typechecks both branches
instead of declaring one of them dead.

## Contained, checked at the moment of use

`REQ-021` opens files *this application downloaded*, and `is_contained` is asked again here rather
than trusted from when the record was written. A `history` row is durable and the world is not: the
output directory can be reconfigured, and a stored path is data like any other. `SEC-001`'s posture
is that the boundary is checked where it is crossed.

## Failure is reported, never silent

A file that has been moved or deleted is the *ordinary* case for a history record — `UX-001` says
remove never deletes a file, so the user is free to move their downloads and often will. Answering
with a reason the caller can show is the whole contract; `NFR-006` applies to this surface as much
as to an extractor's message.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Protocol

from tracks_and_trails.core.paths import is_contained

#: How long to wait for the launcher to *start*. It is not the file manager's lifetime — that
#: outlives us — only the moment between spawning and knowing whether spawning worked.
LAUNCH_TIMEOUT_SECONDS: Final = 10.0

#: The one D-Bus call that selects a file in a Linux file manager, and the tool that makes it.
DBUS_TOOL: Final = "dbus-send"


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
            f"{path} is no longer there. It may have been moved, renamed or deleted — nothing in "
            "Tracks & Trails removes your files, so the record is kept either way."
        )
    return None


def open_file(
    path: Path,
    *,
    within: Path,
    run: Spawner | None = None,
    platform: str = sys.platform,
) -> Refusal | None:
    """Open `path` in whatever the desktop uses for it. `None` means it was launched."""
    refusal = _refuse_unless_usable(path, within)
    if refusal is not None:
        return refusal
    return _spawn(open_command(path, platform), run)


def reveal_file(
    path: Path,
    *,
    within: Path,
    run: Spawner | None = None,
    platform: str = sys.platform,
) -> Refusal | None:
    """Show `path` in the file manager, selected. `None` means it was launched."""
    refusal = _refuse_unless_usable(path, within)
    if refusal is not None:
        return refusal
    return _spawn(reveal_command(path, platform), run)


def open_command(path: Path, platform: str = sys.platform) -> list[str]:
    """The argv for opening. **A list, always** — see the module docstring."""
    if platform == "win32":
        # `explorer <path>` opens the file with its associated application. `start` is a `cmd`
        # builtin and is deliberately not used: reaching it means going through a shell, which is
        # exactly the boundary this module refuses to cross.
        return ["explorer", str(path)]
    # No macOS branch: `REQUIREMENTS.md` §7 defers macOS beyond Phase 5, and a branch for a platform
    # nothing supports would look like support without being it.
    return ["xdg-open", str(path)]


def reveal_command(path: Path, platform: str = sys.platform) -> list[str]:
    """The argv for revealing, which is the platform-specific half.

    **`explorer /select,<path>` is one argument, comma and all.** Windows' shell parses the comma;
    splitting it into two argv elements silently opens the *parent folder* without selecting
    anything, which looks close enough to working to survive a careless test.

    On Linux the D-Bus `FileManager1` interface is what selects a file, and `dbus-send` is the call
    that needs no new dependency. **When it is absent the parent directory is opened instead** —
    which selects nothing, and is the honest degradation rather than a failure: the user asked to
    find their file, and the folder holding it answers most of that.
    """
    if platform == "win32":
        return ["explorer", f"/select,{path}"]
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
    if code:
        detail = (getattr(completed, "stderr", "") or "").strip()
        return Refusal(
            f"Your file manager reported an error (exit {code})." + (f" {detail}" if detail else "")
        )
    return None
