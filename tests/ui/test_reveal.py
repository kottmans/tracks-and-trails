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
import sys
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
    start_associated,
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

    assert open_file(path, within=downloads, run=spawner, platform="linux") is None

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

    This asserts the real path once, so the seam is known to be wired to something.

    **It used to run `true`, on the strength of *"on every Linux image"* — and it has no platform
    guard.** On Windows there is no such command, and this passed on the `windows desktop` job
    only because that job's steps run under Git bash, which puts Git's `usr/bin` directory on
    `PATH`. Run through `cmd` instead it fails with `FileNotFoundError [WinError 2]`, which is
    how it was found (`STARBASE`, 2026-09-12). A test that depends on which shell invoked pytest
    is a test that will break for a reason unrelated to what it asserts.

    `sys.executable -c ""` is on every machine that can run this suite, by construction.
    """
    completed = _run([sys.executable, "-c", ""], capture_output=True, text=True, check=False)

    assert completed.returncode == 0


# --- criterion 4: nothing outside the output directory ----------------------------------------


def test_a_path_outside_the_download_folder_is_refused(tmp_path: Path, downloads: Path) -> None:
    """`SEC-001`, checked here rather than trusted from when the record was written."""
    elsewhere = tmp_path / "secrets.txt"
    elsewhere.write_text("private")
    spawner = RecordingSpawner()

    for act in (open_file, reveal_file):
        refusal = act(elsewhere, within=downloads, run=spawner, platform="linux")
        assert refusal is not None
        assert "outside the download folder" in refusal.reason

    assert spawner.calls == [], "a refused path still reached the launcher"


def test_a_traversal_out_of_the_download_folder_is_refused(downloads: Path) -> None:
    """`../` is the spelling an attacker uses and `is_contained` resolves before comparing."""
    spawner = RecordingSpawner()
    escape = downloads / ".." / "escaped.mp4"

    refusal = open_file(escape, within=downloads, run=spawner, platform="linux")

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
        open_file(  # type: ignore[union-attr]
            candidate, within=downloads, run=RecordingSpawner(), platform="linux"
        ).reason
        for candidate in (missing_outside, present_outside)
    }

    assert all("outside the download folder" in reason for reason in reasons)
    assert not any("no longer there" in reason for reason in reasons), (
        "the refusal distinguishes an existing file from a missing one outside the folder, which "
        "makes this a probe for whether any path on the machine exists"
    )


# --- criterion 3: a moved or deleted file says so ---------------------------------------------


def test_a_file_that_has_been_moved_says_so(downloads: Path) -> None:
    """The ordinary case for any stored path: `UX-001` means users move their downloads freely."""
    spawner = RecordingSpawner()
    gone = downloads / "moved-away.mp4"

    refusal = reveal_file(gone, within=downloads, run=spawner)

    assert refusal is not None
    assert "no longer there" in refusal.reason
    assert "moved" in refusal.reason
    assert spawner.calls == []


def test_a_missing_launcher_says_which_one(downloads: Path) -> None:
    """A machine with no `xdg-open` is a real configuration, not a broken one.

    **The platform is pinned rather than derived.** This is the POSIX route specifically — Windows
    Open does not run a launcher at all (`T086-R1`) — so naming `xdg-open` is now correct instead
    of being the Linux-only assumption that made this the last of the 38 Windows failures to fall.
    """
    path = downloads / "clip.mp4"
    path.write_bytes(b"")

    refusal = open_file(
        path, within=downloads, run=RaisingSpawner(FileNotFoundError()), platform="linux"
    )

    assert refusal is not None
    assert "xdg-open" in refusal.reason
    assert "not installed" in refusal.reason


def test_a_launcher_that_fails_reports_its_exit_code_and_message(downloads: Path) -> None:
    """`xdg-open` exits 3 when nothing is configured for the type, and says nothing itself."""
    path = downloads / "clip.mp4"
    path.write_bytes(b"")

    refusal = open_file(
        path,
        within=downloads,
        run=RecordingSpawner(returncode=3, stderr="no application"),
        platform="linux",
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
        platform="linux",
    )

    assert refusal is not None
    assert "did not respond" in refusal.reason


def test_an_os_error_is_reported_rather_than_raising(downloads: Path) -> None:
    """`PermissionError` on a noexec mount, and every other `OSError` the kernel can produce."""
    path = downloads / "clip.mp4"
    path.write_bytes(b"")

    refusal = open_file(
        path, within=downloads, run=RaisingSpawner(PermissionError("denied")), platform="linux"
    )

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
    # The line that used to sit here — `open_command(path, "win32") == ["explorer", str(path)]` —
    # asserted the `T086-R1` defect. Windows Open takes no argv now; see
    # `test_windows_open_uses_the_associated_application_api_and_builds_no_argv`.


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


# --- T086-R1: Windows Open takes the associated-application route ------------------------------


def test_windows_open_uses_the_associated_application_api_and_builds_no_argv(
    downloads: Path,
) -> None:
    """**`T086-R1`.** `explorer <path>` navigates the file manager; it does not open the file.

    Windows' documented associated-application operations are `ShellExecuteW`'s `open` verb and
    `os.startfile`, which wraps it. The previous implementation ran `explorer` and *asserted in a
    comment* that this opened the associated application — a claim an argv test cannot reach, which
    is why it survived a green Windows job.

    Asserted from Linux through the injected starter: the file goes to the start route, and **no
    argv is built at all**, which is what distinguishes this from the defect.
    """
    path = downloads / "clip.mp4"
    path.write_bytes(b"")
    started: list[Path] = []
    spawner = RecordingSpawner()

    assert (
        open_file(
            path,
            within=downloads,
            run=spawner,
            start=started.append,
            platform="win32",
        )
        is None
    )

    assert started == [path]
    assert spawner.calls == [], (
        "Windows Open built an argv; the associated-application API takes none"
    )


def test_windows_open_still_refuses_a_path_outside_the_download_folder(
    downloads: Path, tmp_path: Path
) -> None:
    """Containment is checked before either route, so the new branch cannot bypass `SEC-001`."""
    outside = tmp_path / "elsewhere.mp4"
    outside.write_bytes(b"")
    started: list[Path] = []

    refusal = open_file(outside, within=downloads, start=started.append, platform="win32")

    assert refusal is not None
    assert "outside the download folder" in refusal.reason
    assert started == []


def test_a_file_type_with_no_associated_application_is_reported(downloads: Path) -> None:
    """`os.startfile` raises `OSError` when nothing is registered for the extension.

    An ordinary configuration rather than a fault — and a refusal a user can act on, rather than an
    exception out of a Qt slot.
    """
    path = downloads / "clip.unknownext"
    path.write_bytes(b"")

    def refuse(_: Path) -> None:
        raise OSError("no application is associated with this file")

    refusal = open_file(path, within=downloads, start=refuse, platform="win32")

    assert refusal is not None
    assert "could not open" in refusal.reason
    assert "clip.unknownext" in refusal.reason


def test_the_default_windows_starter_calls_os_startfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**The seam is wired to the real API**, asserted by *calling* it.

    The first version scraped `inspect.getsource` for the string `os.startfile` — which appears in
    this function's own docstring, so deleting the call left the test passing. Vacuous, and exactly
    the class `docs/project/TESTING.md` §13 records.

    `os.startfile` is replaced and the dispatch observed — on any platform, because the launcher is
    looked up at call time rather than bound behind a module-level platform split.
    """
    import os

    target = tmp_path / "whatever.mp4"
    launched: list[object] = []
    # `raising=False` so this works on Linux too, where the attribute does not exist. That is the
    # point of the seam being one definition rather than a platform split: a mutation deleting the
    # call is killed on every platform, not only on the Windows job.
    monkeypatch.setattr(os, "startfile", launched.append, raising=False)

    start_associated(target)

    assert launched == [target], "the Windows starter did not reach os.startfile"


def test_open_never_runs_explorer_on_any_platform(downloads: Path) -> None:
    """`explorer` belongs to Reveal alone now. Stated as an exclusion so it cannot drift back."""
    path = downloads / "clip.mp4"

    assert "explorer" not in open_command(path, "win32")
    assert "explorer" not in open_command(path, "linux")
    assert reveal_command(path, "win32")[0] == "explorer"


def test_the_windows_starter_refuses_where_os_startfile_does_not_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Absence is the ordinary case off Windows, and it **raises** rather than passing quietly.

    `open_file` routes here only for `win32`, so reaching it elsewhere means something is wrong —
    and a launcher that returns cleanly without launching is the exact failure this module exists
    to prevent.
    """
    import os

    monkeypatch.delattr(os, "startfile", raising=False)

    with pytest.raises(OSError, match="Windows-only"):
        start_associated(tmp_path / "whatever.mp4")
