"""Opening and revealing a completed file (`T-086`, `REQ-021`).

One test per acceptance criterion. **No `QApplication` anywhere in this file** — `reveal.py` imports
no Qt, and that separation is what lets the argv assertions run on any machine, including the
Windows argv, which is the detail most likely to be written wrongly and the hardest to check.

Nothing here launches a file manager. `run` is injected, and what is asserted is the **argv list**:
the risk in this module is a path becoming an argument boundary, and that is visible in the list
long before it is visible in a launched process.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import pytest

from tracks_and_trails.ui.reveal import (
    DBUS_TOOL,
    LAUNCH_TIMEOUT_SECONDS,
    Refusal,
    _run,
    dbus_available,
    open_command,
    open_file,
    reveal_command,
    reveal_file,
)


class RecordingSpawner:
    """A `Spawner` that records what it was asked to launch and launches nothing."""

    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.calls: list[tuple[list[str], dict[str, Any]]] = []
        self._result = subprocess.CompletedProcess[str](
            args=[], returncode=returncode, stdout="", stderr=stderr
        )

    def __call__(self, args: list[str], /, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append((list(args), dict(kwargs)))
        return self._result

    @property
    def argv(self) -> list[str]:
        assert len(self.calls) == 1, f"expected one launch, got {len(self.calls)}"
        return self.calls[0][0]


class RaisingSpawner:
    """A `Spawner` that fails the way a real one does."""

    def __init__(self, error: BaseException) -> None:
        self._error = error

    def __call__(self, args: list[str], /, **kwargs: Any) -> Any:
        raise self._error


@pytest.fixture
def downloads(tmp_path: Path) -> Path:
    directory = tmp_path / "Downloads"
    directory.mkdir()
    return directory


#: Titles yt-dlp really produces, each of which is an argument boundary somewhere if a shell is
#: ever reached. The leading dash is the one that matters most: `xdg-open -- rude.mp4` would be
#: read as an option, and a *shell* is not needed for that to go wrong.
HOSTILE_NAMES = [
    'a "quoted" title.mp4',
    "a title with spaces.mp4",
    "-leading-dash.mp4",
    "semicolon; rm -rf ~.mp4",
    "back`tick`.mp4",
    "dollar $HOME sign.mp4",
    "pipe | and & ampersand.mp4",
    "newline\nin the title.mp4",
]


# --- criterion 2: a hostile path is passed intact and executes nothing ------------------------


@pytest.mark.parametrize("name", HOSTILE_NAMES)
@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_a_hostile_name_is_one_whole_argv_element(
    name: str, platform: str, downloads: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**The criterion, on both platforms, without needing either of them.**

    Asserted as *containment in a single element* rather than as an exact argv, because what
    matters is that no separator split it — `explorer /select,<path>` carries the path inside a
    larger element by design, and an exact-match assertion would have to know which.

    Elements are percent-decoded first: the D-Bus arm passes a `file://` URI, so `a title.mp4`
    legitimately appears as `a%20title.mp4`. Decoding checks the *whole path survived*, which is
    the actual criterion, rather than checking the spelling it survived in.

    `dbus_available` is pinned so the argv under test is the machine-independent one; the fallback
    has its own test, and it names the parent folder rather than the file.
    """
    monkeypatch.setattr("tracks_and_trails.ui.reveal.dbus_available", lambda: True)
    # **Not written to disk.** The command builders are pure functions of the path, and Windows
    # refuses `"`, `|` and a newline in a filename outright — so creating the fixture would make
    # this test fail on the platform whose argv it exists to check. The names still have to be
    # tested there: `explorer /select,` is the argument most likely to be split.
    path = downloads / name

    opened = open_command(path, platform)
    revealed = reveal_command(path, platform)

    # Separators normalised before comparing. `as_uri()` renders a Windows path with forward
    # slashes while `str(path)` uses backslashes, so the raw comparison found nothing on the
    # Windows job — and the assertion below would have reported "spread across 0 arguments",
    # which describes a defect that is not there.
    wanted = str(path).replace("\\", "/")
    for argv in (opened, revealed):
        holding = [element for element in argv if wanted in unquote(element).replace("\\", "/")]
        assert len(holding) == 1, f"{argv} spread the path across {len(holding)} arguments"
        # And nothing was quoted *into* the element by us: a caller adding quotes to survive a
        # shell is the tell that a shell is expected somewhere.
        assert not holding[0].startswith('"'), f"{argv} quotes the path, so a shell is assumed"


def test_no_shell_is_ever_used(downloads: Path) -> None:
    """`shell=False` is passed explicitly, and asserted, because the default is not the promise."""
    path = downloads / "clip.mp4"
    path.write_bytes(b"")
    spawner = RecordingSpawner()

    assert open_file(path, within=downloads, run=spawner) is None

    _, kwargs = spawner.calls[0]
    assert kwargs["shell"] is False
    assert kwargs["timeout"] == LAUNCH_TIMEOUT_SECONDS


def test_the_default_spawner_refuses_a_shell_rather_than_documenting_that_it_will_not() -> None:
    """`_run` pins `shell=False`, and the guard is reachable — so it is fired here.

    `ruff`'s `S603` on that call is answered by this behaviour rather than by a comment; a
    suppression that nothing tests is the same claim with no evidence behind it.
    """
    with pytest.raises(ValueError, match="never runs a command through a shell"):
        # `S604` is exactly what this asserts is refused, so the suppression is the point.
        _run(["true"], shell=True)  # noqa: S604


def test_the_default_spawner_actually_runs_the_command() -> None:
    """The injected-spawner tests would all pass against a `_run` that did nothing.

    `true` is on every Linux image and exits 0; this asserts the real path once so the seam is
    known to be wired to something.
    """
    completed = _run(["true"], capture_output=True, text=True, check=False)

    assert completed.returncode == 0


# --- criterion 4: nothing outside the output directory ----------------------------------------


def test_a_path_outside_the_download_folder_is_refused(tmp_path: Path, downloads: Path) -> None:
    """`SEC-001`, checked here rather than trusted from when the record was written."""
    elsewhere = tmp_path / "secrets.txt"
    elsewhere.write_text("private")
    spawner = RecordingSpawner()

    for act in (open_file, reveal_file):
        refusal = act(elsewhere, within=downloads, run=spawner)
        assert refusal is not None
        assert "outside the download folder" in refusal.reason

    assert spawner.calls == [], "a refused path still reached the launcher"


def test_a_traversal_out_of_the_download_folder_is_refused(downloads: Path) -> None:
    """`../` is the spelling an attacker uses and `is_contained` resolves before comparing."""
    spawner = RecordingSpawner()
    escape = downloads / ".." / "escaped.mp4"

    refusal = open_file(escape, within=downloads, run=spawner)

    assert refusal is not None
    assert spawner.calls == []


def test_containment_is_checked_before_existence(tmp_path: Path, downloads: Path) -> None:
    """**The order is the property**, not an implementation detail.

    A refusal that said "no such file" for a path outside the folder and "outside the folder" for
    one inside it would answer, for any path on the machine, whether that path exists. Both cases
    must give the *containment* answer.
    """
    missing_outside = tmp_path / "does-not-exist.mp4"
    present_outside = tmp_path / "exists.mp4"
    present_outside.write_bytes(b"")

    reasons = {
        open_file(candidate, within=downloads, run=RecordingSpawner()).reason  # type: ignore[union-attr]
        for candidate in (missing_outside, present_outside)
    }

    assert all("outside the download folder" in reason for reason in reasons)
    assert not any("no longer there" in reason for reason in reasons), (
        "the refusal distinguishes an existing file from a missing one outside the folder, which "
        "makes this a probe for whether any path on the machine exists"
    )


# --- criterion 3: a moved or deleted file says so ---------------------------------------------


def test_a_file_that_has_been_moved_says_so(downloads: Path) -> None:
    """The ordinary case for a history record: `UX-001` means users move their downloads freely."""
    spawner = RecordingSpawner()
    gone = downloads / "moved-away.mp4"

    refusal = reveal_file(gone, within=downloads, run=spawner)

    assert refusal is not None
    assert "no longer there" in refusal.reason
    assert "moved" in refusal.reason
    assert spawner.calls == []


def test_a_missing_launcher_says_which_one(downloads: Path) -> None:
    """A machine with no launcher is a real configuration, not a broken one.

    **The launcher is named from this platform's own builder**, not written out. Hardcoding
    `xdg-open` is what made this the last of the 38 Windows failures to fall: `explorer` is what
    `command[0]` is there, so the assertion described a message the code never produces.
    """
    path = downloads / "clip.mp4"
    path.write_bytes(b"")

    refusal = open_file(path, within=downloads, run=RaisingSpawner(FileNotFoundError()))

    assert refusal is not None
    assert open_command(path)[0] in refusal.reason, (
        f"the refusal does not name the launcher that is missing: {refusal.reason}"
    )
    assert "not installed" in refusal.reason


def test_a_launcher_that_fails_reports_its_exit_code_and_message(downloads: Path) -> None:
    """`xdg-open` exits 3 when nothing is configured for the type, and says nothing itself."""
    path = downloads / "clip.mp4"
    path.write_bytes(b"")

    refusal = open_file(
        path, within=downloads, run=RecordingSpawner(returncode=3, stderr="no application")
    )

    assert refusal is not None
    assert "exit 3" in refusal.reason
    assert "no application" in refusal.reason


def test_a_launcher_that_hangs_is_reported_rather_than_raising(downloads: Path) -> None:
    """`TimeoutExpired` is not an `OSError`, so it needs its own arm — and a raise here would
    cross a Qt slot boundary and be swallowed."""
    path = downloads / "clip.mp4"
    path.write_bytes(b"")

    refusal = open_file(
        path,
        within=downloads,
        run=RaisingSpawner(subprocess.TimeoutExpired(cmd=["xdg-open"], timeout=1.0)),
    )

    assert refusal is not None
    assert "did not respond" in refusal.reason


def test_an_os_error_is_reported_rather_than_raising(downloads: Path) -> None:
    """`PermissionError` on a noexec mount, and every other `OSError` the kernel can produce."""
    path = downloads / "clip.mp4"
    path.write_bytes(b"")

    refusal = open_file(path, within=downloads, run=RaisingSpawner(PermissionError("denied")))

    assert refusal is not None
    assert "denied" in refusal.reason


# --- criterion 1: what each platform is actually asked to do ----------------------------------


def test_windows_reveal_keeps_select_and_the_path_in_one_argument(downloads: Path) -> None:
    """**The single most breakable line in the module** (`T-086`).

    `explorer /select, <path>` as two arguments opens the parent folder without selecting
    anything — which looks close enough to working that a manual check on Windows can miss it.
    Asserted exactly, and from Linux.
    """
    path = downloads / "A clip.mp4"

    assert reveal_command(path, "win32") == ["explorer", f"/select,{path}"]
    assert open_command(path, "win32") == ["explorer", str(path)]


def test_linux_reveal_asks_the_file_manager_to_select_the_file(
    downloads: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-Bus `ShowItems` is what selects a file; `xdg-open` on the file would *open* it instead."""
    monkeypatch.setattr("tracks_and_trails.ui.reveal.dbus_available", lambda: True)
    path = downloads / "A clip.mp4"

    argv = reveal_command(path, "linux")

    assert argv[0] == DBUS_TOOL
    assert "org.freedesktop.FileManager1.ShowItems" in argv
    assert f"array:string:{path.as_uri()}" in argv
    # `as_uri` percent-encodes, which is how the space survives D-Bus's own parsing.
    assert "%20" in path.as_uri()


def test_linux_reveal_falls_back_to_the_folder_when_dbus_is_absent(
    downloads: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fallback the docstring promises, which is the whole reason it is asserted."""
    monkeypatch.setattr("tracks_and_trails.ui.reveal.dbus_available", lambda: False)
    path = downloads / "A clip.mp4"

    assert reveal_command(path, "linux") == ["xdg-open", str(downloads)]


def test_dbus_availability_is_read_from_the_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """The seam itself, so the two tests above are not pinning a stub to another stub."""
    monkeypatch.setattr("tracks_and_trails.ui.reveal.shutil.which", lambda tool: None)
    assert not dbus_available()
    monkeypatch.setattr("tracks_and_trails.ui.reveal.shutil.which", lambda tool: f"/usr/bin/{tool}")
    assert dbus_available()


def test_linux_open_uses_xdg_open(downloads: Path) -> None:
    """The desktop-agnostic launcher, and no macOS branch: §7 defers that platform."""
    path = downloads / "clip.mp4"

    assert open_command(path, "linux") == ["xdg-open", str(path)]
    assert open_command(path, "darwin") == ["xdg-open", str(path)], (
        "a macOS branch was added without `REQUIREMENTS.md` §7 changing"
    )


def test_a_refusal_is_a_value_not_an_exception() -> None:
    """The contract callers in Qt slots depend on: raising out of a slot is swallowed."""
    assert issubclass(Refusal, object)
    assert not issubclass(Refusal, BaseException)
