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
    ACTIVATE_ACTION,
    DBUS_TOOL,
    DOLPHIN_CLASS,
    activate_command,
    answered_true,
    candidate_uuids,
    instance_showing,
    pid_of,
    raise_the_file_manager,
    window_of,
)

#: Every call in these tests supplies this, so a machine without `dbus-send` — every Windows
#: runner — answers the same as one with it (`T347-R5`). Asking the running machine made the same
#: test assert one thing on Linux and another on Windows, and the Windows job failed on it.
INSTALLED = lambda: True  # noqa: E731 - a seam, and a def here would read as a helper

#: What `dbus-send --print-reply=literal` prints for the bus's name list, trimmed to the shape the
#: reader cares about: two Dolphin instances and something that is not one.
NAMES = """
org.freedesktop.DBus org.kde.KWin org.kde.dolphin-4242 org.kde.dolphin-777 org.kde.plasmashell
"""

#: A `WindowsRunner` match list, as the tool prints it. **Both records are activations**: the
#: leading integer is the action KWin will perform, and `0` is the only one this application asks
#: for.
MATCHES = """
array [ struct { 0_{aaaaaaaa-0000-0000-0000-000000000001} downloads — Dolphin org.kde.dolphin
int32 100 double 0.8 array [ ] } struct { 0_{bbbbbbbb-0000-0000-0000-000000000002} other — Dolphin
org.kde.dolphin int32 30 double 0.7 array [ ] } ]
"""

#: The reviewer's counterexample (`T347-R3`): a window whose **caption** carries an id shaped like
#: a close action, ahead of the genuine activation record for the target.
MATCHES_WITH_A_CLOSE_IN_A_CAPTION = """
array [ struct { 0_{cccccccc-0000-0000-0000-000000000003}
1_{bbbbbbbb-0000-0000-0000-000000000002} — Dolphin org.kde.dolphin int32 100 double 0.8 array [ ] }
struct { 0_{bbbbbbbb-0000-0000-0000-000000000002} other — Dolphin org.kde.dolphin int32 30
double 0.7 array [ ] } ]
"""


#: A caption that forges a **record boundary** (`T347-R3`, second pass). `--print-reply=literal`
#: emits strings unquoted, so the text `struct {` inside a caption opens an apparent record and the
#: id after it reaches the candidate list. The genuine window for the pid follows it.
MATCHES_WITH_A_FORGED_RECORD = """
array [ struct { 0_{cccccccc-0000-0000-0000-000000000003} a folder called struct {
0_{eeeeeeee-0000-0000-0000-000000000005} — Dolphin org.kde.dolphin int32 100 double 0.8 array [ ] }
struct { 0_{bbbbbbbb-0000-0000-0000-000000000002} other — Dolphin org.kde.dolphin int32 30
double 0.7 array [ ] } ]
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
    argv = activate_command("aaaa")

    assert argv[0] == DBUS_TOOL
    assert "--dest=org.kde.KWin" in argv
    assert "org.kde.krunner1.Run" in argv
    assert "string:0_{aaaa}" in argv


def test_the_action_is_built_here_and_never_taken_from_kwin() -> None:
    """`T347-R3`: the leading integer in a match id is an **instruction**, not a name.

    KWin's runner defines `ActivateAction` first and `CloseAction` second, and `Run` reads that
    integer out of the id it is given. This module used to pass a captured id straight through,
    so text that merely looked like an id — in a window caption — could have asked KWin to close a
    window. The action is this application's constant now, and only the uuid comes from KWin.
    """
    argv = activate_command("1_{bbbb}")

    assert f"string:{ACTIVATE_ACTION}_{{1_{{bbbb}}}}" in argv, (
        f"a uuid that itself looks like a close action still produced an activation, argv: {argv}"
    )
    assert not any(argument.startswith("string:1_") for argument in argv)


def test_a_close_action_in_a_caption_is_not_a_candidate() -> None:
    """The reviewer's counterexample, as a test: captions are not where ids live."""
    uuids = candidate_uuids(MATCHES_WITH_A_CLOSE_IN_A_CAPTION)

    assert uuids == [
        "cccccccc-0000-0000-0000-000000000003",
        "bbbbbbbb-0000-0000-0000-000000000002",
    ], f"an id inside a caption was read as a match: {uuids}"


def test_a_forged_record_reaches_the_candidate_list_and_dies_at_kwin() -> None:
    """What the parser does **not** promise, and what does (`T347-R3`, second pass).

    The reviewer's correction: splitting on the literal `struct {` is a heuristic, so this test
    asserts the uncomfortable half first — the forged id really is a candidate — and then that it
    gets no further. `window_of` activates nothing until KWin itself says the uuid is a Dolphin
    window belonging to the pid that answered, and a caption cannot make KWin say that.
    """
    forged = "eeeeeeee-0000-0000-0000-000000000005"

    assert forged in candidate_uuids(MATCHES_WITH_A_FORGED_RECORD), (
        "the caption no longer reaches the candidate list, so the rest of this proves nothing"
    )

    desktop = FakeDesktop(
        {
            "org.kde.krunner1.Match": MATCHES_WITH_A_FORGED_RECORD,
            "cccccccc": window_info(999),
            "eeeeeeee": "Error org.freedesktop.DBus.Error.InvalidArgs: no such window",
            "bbbbbbbb": window_info(777),
        }
    )

    assert window_of(777, lambda argv: desktop(argv).stdout) == (
        "bbbbbbbb-0000-0000-0000-000000000002"
    ), "a forged candidate displaced the window KWin actually confirmed"


def test_a_forged_record_is_not_a_window_when_none_answers_for_the_process() -> None:
    """And when no genuine window matches, the forged one does not stand in for it."""
    desktop = FakeDesktop(
        {
            "org.kde.krunner1.Match": MATCHES_WITH_A_FORGED_RECORD,
            "cccccccc": window_info(999),
            "eeeeeeee": "Error org.freedesktop.DBus.Error.InvalidArgs: no such window",
            "bbbbbbbb": window_info(999),
        }
    )

    assert window_of(777, lambda argv: desktop(argv).stdout) is None


def test_only_activation_records_are_candidates() -> None:
    """A record whose own action is not activation is not a window this application may act on."""
    closing = """
    array [ struct { 1_{dddddddd-0000-0000-0000-000000000004} downloads — Dolphin org.kde.dolphin
    int32 100 double 0.8 array [ ] } ]
    """

    assert candidate_uuids(closing) == []


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


class OnePerInstance:
    """A `Spawner` answering `isItemVisibleInAnyView` per Dolphin instance, and the rest by key.

    Per instance because that is the question `T347-R1` turns on: several instances can be asked,
    and the answer that matters is **how many** say yes.
    """

    def __init__(
        self, visible_to: dict[str, bool | str], answers: dict[str, str] | None = None
    ) -> None:
        self.visible_to = visible_to
        self.answers = answers or {}
        self.asked: list[list[str]] = []

    def __call__(self, args: list[str], /, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.asked.append(list(args))
        reply = ""
        if any("ListNames" in argument for argument in args):
            reply = NAMES
        elif any("isItemVisibleInAnyView" in argument for argument in args):
            name = next(a.removeprefix("--dest=") for a in args if a.startswith("--dest="))
            # A bool is that instance's yes or no; a **string** is its literal reply, which is how
            # a test says "this one did not answer" — the case `T347-R1`'s second pass is about.
            answer = self.visible_to.get(name, False)
            reply = answer if isinstance(answer, str) else f"   boolean {answer}".lower()
        else:
            for key, value in self.answers.items():
                if any(key in argument for argument in args):
                    reply = value
                    break
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=reply, stderr="")

    def method_calls(self, fragment: str) -> list[list[str]]:
        return [argv for argv in self.asked if any(fragment in argument for argument in argv)]


def test_the_one_instance_showing_the_file_is_the_one_chosen(folder: Path) -> None:
    """The question is the **file**, because that is what the reveal selected (`T347-R1`)."""
    desktop = OnePerInstance({"org.kde.dolphin-4242": True})

    found = instance_showing(folder / "clip.mp4", lambda argv: desktop(argv).stdout)

    assert found == "org.kde.dolphin-4242"


def test_two_instances_showing_the_file_decline_rather_than_guess(folder: Path) -> None:
    """`T347-R1`: several instances can show one file, and the reveal went to exactly one.

    Dolphin picks its recipient by walking from the active window and testing item visibility, not
    by any order this application can reproduce from outside. Raising the first would bring forward
    a window that may be showing an entirely different current tab, so an ambiguous answer raises
    nothing at all.
    """
    desktop = OnePerInstance({"org.kde.dolphin-4242": True, "org.kde.dolphin-777": True})

    assert instance_showing(folder / "clip.mp4", lambda argv: desktop(argv).stdout) is None


@pytest.mark.parametrize(
    ("reply", "what"),
    [
        ("", "a question that timed out"),
        ("Error org.freedesktop.DBus.Error.NoReply: did not receive a reply", "an error"),
    ],
)
def test_an_instance_that_does_not_answer_leaves_uniqueness_unestablished(
    folder: Path, reply: str, what: str
) -> None:
    """`T347-R1`, second pass: one yes and one unknown is not one yes.

    Every instance that could not answer is an instance that might also be showing the file, and
    this cannot tell which of them the reveal went to. Counting silence as a no let a single
    positive look unique, which is exactly the guess the whole function refuses to make.
    """
    desktop = OnePerInstance({"org.kde.dolphin-4242": True, "org.kde.dolphin-777": reply})

    found = instance_showing(folder / "clip.mp4", lambda argv: desktop(argv).stdout)

    assert found is None, f"{what} counted as a no, and one positive was taken as unique: {found}"


def test_no_instance_showing_the_file_is_no_answer(folder: Path) -> None:
    """The common case: the reveal has just opened a window, which is already in front."""
    desktop = OnePerInstance({})

    assert instance_showing(folder / "clip.mp4", lambda argv: desktop(argv).stdout) is None


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

    assert found == "bbbbbbbb-0000-0000-0000-000000000002"


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
    desktop = OnePerInstance(
        {"org.kde.dolphin-4242": True},
        {
            "org.kde.krunner1.Match": MATCHES,
            "aaaaaaaa": window_info(4242),
            "bbbbbbbb": window_info(777),
        },
    )

    assert (
        raise_the_file_manager(
            folder / "clip.mp4", run=desktop, platform="linux", available=INSTALLED
        )
        is True
    )
    runs = desktop.method_calls("org.kde.krunner1.Run")
    assert len(runs) == 1
    assert "string:0_{aaaaaaaa-0000-0000-0000-000000000001}" in runs[0]


def test_nothing_is_asked_on_windows(folder: Path) -> None:
    """Windows reveals through Explorer, which raises its own window."""
    desktop = FakeDesktop({})

    assert (
        raise_the_file_manager(
            folder / "clip.mp4", run=desktop, platform="win32", available=INSTALLED
        )
        is False
    )
    assert desktop.asked == []


def test_a_desktop_that_answers_nothing_changes_nothing(folder: Path) -> None:
    """No KWin, no Dolphin, no D-Bus at all: the reveal stands as it did."""
    desktop = FakeDesktop({})

    assert (
        raise_the_file_manager(
            folder / "clip.mp4", run=desktop, platform="linux", available=INSTALLED
        )
        is False
    )
    assert desktop.method_calls("org.kde.krunner1.Run") == []


def test_no_window_carrying_that_pid_is_left_alone(folder: Path) -> None:
    """KWin is there and one instance shows the file, but no window matches. Nothing happens."""
    desktop = OnePerInstance(
        {"org.kde.dolphin-4242": True},
        {
            "org.kde.krunner1.Match": MATCHES,
            "aaaaaaaa": window_info(9999),
            "bbbbbbbb": window_info(9999),
        },
    )

    assert (
        raise_the_file_manager(
            folder / "clip.mp4", run=desktop, platform="linux", available=INSTALLED
        )
        is False
    )
    assert desktop.method_calls("org.kde.krunner1.Run") == []


def test_a_desktop_that_raises_is_not_an_error_the_user_sees(folder: Path) -> None:
    """The raise is a convenience. A failure to ask is not worth a refusal on screen."""

    def explode(args: list[str], /, **kwargs: Any) -> Any:
        raise OSError("no session bus")

    assert (
        raise_the_file_manager(
            folder / "clip.mp4", run=explode, platform="linux", available=INSTALLED
        )
        is False
    )
