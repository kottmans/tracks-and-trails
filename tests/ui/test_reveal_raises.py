"""Bringing an already-open file manager window forward (`T-347`, `ui/reveal.py`).

Measured on KDE Plasma Wayland — the desktop the report came from — and recorded in
`docs/project/evidence/2026-09-18-T347-raising-dolphin.md`: when no window shows the folder,
`ShowItems` opens one and it arrives in front; when one **already** shows it, that window is reused
and left where it was, behind another window or minimized. The maintainer ruled the narrow KWin
route on 2026-09-18.

**These tests are about the decision, not the desktop.** Every D-Bus question goes through the
module's `Spawner` seam, so a fake answers them and the argv, the identity rule and every
do-nothing path are asserted on any machine. The desktop half — that KWin actually raises the
window — is `tools/dolphin_raise_probe.py`, which no runner can execute.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from tracks_and_trails.ui.reveal import (
    DBUS_TOOL,
    DOLPHIN_CLASS,
    activate_command,
    answered_true,
    instance_showing,
    pid_of,
    raise_the_file_manager,
    window_of,
)

#: What `dbus-send --print-reply=literal` prints for the bus's name list, trimmed to the shape the
#: reader cares about: two Dolphin instances and something that is not one.
NAMES = """
org.freedesktop.DBus org.kde.KWin org.kde.dolphin-4242 org.kde.dolphin-777 org.kde.plasmashell
"""

#: A `WindowsRunner` match list, as the tool prints it.
MATCHES = """
array [ struct { 0_{aaaaaaaa-0000-0000-0000-000000000001} downloads — Dolphin org.kde.dolphin
int32 100 double 0.8 array [ ] } struct { 1_{bbbbbbbb-0000-0000-0000-000000000002} other — Dolphin
org.kde.dolphin int32 30 double 0.7 array [ ] } ]
"""


def window_info(pid: int, resource_class: str = DOLPHIN_CLASS) -> str:
    return (
        "array [ dict entry( resourceClass variant "
        f"{resource_class} ) dict entry( pid variant int32 {pid} ) "
        "dict entry( minimized variant boolean false ) ]"
    )


class FakeDesktop:
    """A `Spawner` that answers D-Bus questions from a script and records what it was asked.

    Keyed on the method name in the argv, because that is what the caller is really choosing;
    matching whole argv lists would make every test restate the module's own command builders.
    """

    def __init__(self, answers: dict[str, str]) -> None:
        self.answers = answers
        self.asked: list[list[str]] = []

    def __call__(self, args: list[str], /, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.asked.append(list(args))
        reply = ""
        for key, value in self.answers.items():
            if any(key in argument for argument in args):
                reply = value
                break
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=reply, stderr="")

    def method_calls(self, fragment: str) -> list[list[str]]:
        return [argv for argv in self.asked if any(fragment in argument for argument in argv)]


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    directory = tmp_path / "Downloads"
    directory.mkdir()
    (directory / "clip.mp4").write_bytes(b"x")
    return directory


# --- the argv, which is what this module is responsible for ------------------------------------


def test_the_activation_asks_kwin_to_run_the_match() -> None:
    argv = activate_command("0_{aaaa}")

    assert argv[0] == DBUS_TOOL
    assert "--dest=org.kde.KWin" in argv
    assert "org.kde.krunner1.Run" in argv
    assert "string:0_{aaaa}" in argv


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("   boolean true", True),
        ("   boolean false", False),
        ("", False),
        # **An error that quotes the path, when the path contains the word.** This is what makes
        # excluding errors load-bearing rather than decorative: a folder named `true` is legal, and
        # without the error check its own failure message would read as a yes and this application
        # would ask KWin to activate a window nobody found.
        (
            'Error org.freedesktop.DBus.Error.InvalidArgs: bad url "file:///home/u/true"',
            False,
        ),
        ("Error org.freedesktop.DBus.Error.ServiceUnknown: no such name", False),
    ],
)
def test_a_reply_is_read_as_true_only_when_it_says_so(text: str, expected: bool) -> None:
    """A reply is a yes only when it is a boolean true, and an error is never a yes."""
    assert answered_true(text) is expected


def test_the_process_id_comes_from_the_bus_name() -> None:
    assert pid_of("org.kde.dolphin-4242") == 4242
    assert pid_of("org.kde.dolphin") is None


# --- finding the right window ------------------------------------------------------------------


def test_the_instance_with_the_folder_open_is_the_one_chosen(folder: Path) -> None:
    desktop = FakeDesktop({"ListNames": NAMES, "isUrlOpen": "   boolean true"})

    assert instance_showing(folder, lambda argv: desktop(argv).stdout) == "org.kde.dolphin-4242"


def test_no_instance_showing_the_folder_is_no_answer(folder: Path) -> None:
    """The common case: the reveal has just opened a window, which is already in front."""
    desktop = FakeDesktop({"ListNames": NAMES, "isUrlOpen": "   boolean false"})

    assert instance_showing(folder, lambda argv: desktop(argv).stdout) is None


def test_the_window_is_found_by_process_id_not_by_title() -> None:
    """`T347-R1`: the match's third member is an **icon name**, so identity comes from `pid`.

    Both matches here are Dolphin windows with the same icon; only one carries the pid. A rule
    that filtered on the icon, or took the first match, would pick the wrong window.
    """
    desktop = FakeDesktop(
        {
            "org.kde.krunner1.Match": MATCHES,
            "aaaaaaaa": window_info(4242),
            "bbbbbbbb": window_info(777),
        }
    )

    found = window_of(777, lambda argv: desktop(argv).stdout)

    assert found == "1_{bbbbbbbb-0000-0000-0000-000000000002}"


def test_a_window_of_another_application_is_not_taken() -> None:
    """`resourceClass` is checked as well, so a window that merely carries the pid is not enough."""
    desktop = FakeDesktop(
        {
            "org.kde.krunner1.Match": MATCHES,
            "aaaaaaaa": window_info(4242, resource_class="org.kde.konsole"),
            "bbbbbbbb": window_info(4242, resource_class="org.kde.konsole"),
        }
    )

    assert window_of(4242, lambda argv: desktop(argv).stdout) is None


# --- the whole route, and every way it declines -------------------------------------------------


def test_the_window_showing_the_folder_is_activated(folder: Path) -> None:
    desktop = FakeDesktop(
        {
            "ListNames": NAMES,
            "isUrlOpen": "   boolean true",
            "org.kde.krunner1.Match": MATCHES,
            "aaaaaaaa": window_info(4242),
            "bbbbbbbb": window_info(777),
        }
    )

    assert raise_the_file_manager(folder / "clip.mp4", run=desktop, platform="linux") is True
    runs = desktop.method_calls("org.kde.krunner1.Run")
    assert len(runs) == 1
    assert "string:0_{aaaaaaaa-0000-0000-0000-000000000001}" in runs[0]


def test_nothing_is_asked_on_windows(folder: Path) -> None:
    """Windows reveals through Explorer, which raises its own window."""
    desktop = FakeDesktop({})

    assert raise_the_file_manager(folder / "clip.mp4", run=desktop, platform="win32") is False
    assert desktop.asked == []


def test_a_desktop_that_answers_nothing_changes_nothing(folder: Path) -> None:
    """No KWin, no Dolphin, no D-Bus at all: the reveal stands as it did."""
    desktop = FakeDesktop({})

    assert raise_the_file_manager(folder / "clip.mp4", run=desktop, platform="linux") is False
    assert desktop.method_calls("org.kde.krunner1.Run") == []


def test_no_window_carrying_that_pid_is_left_alone(folder: Path) -> None:
    """KWin is there and the folder is open, but no window matches. Nothing is activated."""
    desktop = FakeDesktop(
        {
            "ListNames": NAMES,
            "isUrlOpen": "   boolean true",
            "org.kde.krunner1.Match": MATCHES,
            "aaaaaaaa": window_info(9999),
            "bbbbbbbb": window_info(9999),
        }
    )

    assert raise_the_file_manager(folder / "clip.mp4", run=desktop, platform="linux") is False
    assert desktop.method_calls("org.kde.krunner1.Run") == []


def test_a_desktop_that_raises_is_not_an_error_the_user_sees(folder: Path) -> None:
    """The raise is a convenience. A failure to ask is not worth a refusal on screen."""

    def explode(args: list[str], /, **kwargs: Any) -> Any:
        raise OSError("no session bus")

    assert raise_the_file_manager(folder / "clip.mp4", run=explode, platform="linux") is False
