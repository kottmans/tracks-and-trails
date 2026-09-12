"""End-to-end launch and shutdown of the real application (`T-007`).

`tests/ui/test_main_window.py` builds a `MainWindow` inside the test process. This exercises
the path a user actually takes: `app.run` constructs the `QApplication`, shows the window and
enters `exec()`, in a fresh interpreter.

Run as a subprocess deliberately. The acceptance criterion is a **zero exit code and no Qt
warnings on stderr**, and neither is observable in-process: pytest-qt has already created a
`QApplication`, so the real startup path never runs, and Qt's warnings go to the process's
stderr rather than anywhere pytest captures by default.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

#: Runs the real entry point and quits from the GUI thread, with no watcher thread at all.
#:
#: The previous version polled `QApplication.instance()` from a foreign thread. Qt documents
#: `quit()` and `QMetaObject::invokeMethod(..., QueuedConnection)` as thread-safe; it does not
#: document `instance()` as safe to call while the application object is being constructed on
#: another thread, so the harness was relying on something Qt never promised (`T028-R1`).
#:
#: Instead, `MainWindow` is subclassed so that `showEvent` — which Qt calls on the GUI thread,
#: during `show()` — schedules the quit through a zero-delay timer. `app.py` imports
#: `MainWindow` inside `run`, so replacing the module attribute first is enough to have the
#: real entry point construct this subclass.
#:
#: The ordering proof survives and is now directly observable rather than argued: `show()`
#: runs before `exec()`, a zero-delay timer cannot fire until the event loop is running, and
#: both markers are printed in order for the test to assert on.
LAUNCH_AND_QUIT = """
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import tracks_and_trails.ui.main_window as main_window


class QuitOnceShown(main_window.MainWindow):
    def showEvent(self, event):
        super().showEvent(event)
        print("WINDOW-SHOWN", flush=True)
        QTimer.singleShot(0, self._request_quit)

    def _request_quit(self):
        print("QUIT-REQUESTED", flush=True)
        app = QApplication.instance()
        if app is None:
            print("FAIL: no QApplication when the quit fired", file=sys.stderr, flush=True)
            raise SystemExit(3)
        app.quit()


main_window.MainWindow = QuitOnceShown

from tracks_and_trails.app import run

sys.exit(run(["tracks-and-trails"]))
"""


def run_headless(source: str, tmp_home: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        # Redirect platformdirs so a test never writes to the real directories and never reads a
        # window position, a queue or a log the user has of their own.
        #
        # **All three roots, not just config** (`T-131`). This set `XDG_CONFIG_HOME` alone, and the
        # application uses three: `user_config_dir` for `settings.toml` and `window.toml`,
        # `user_data_dir` for **the queue database** and the user-managed yt-dlp copy, and
        # `user_cache_dir` for the application log and the thumbnail cache. So a launch test
        # opened the developer's real database, took the real single-instance lock (`T-087`), and
        # wrote their real log. With the application open the lock is held and the launch hangs
        # until this timeout — which is how it was found, and it would fail the same way on any
        # machine where somebody had the app running.
        #
        # Windows needs its own mechanism: platformdirs resolves folders through
        # SHGetKnownFolderPath via ctypes, so setting APPDATA does nothing there. Its
        # documented escape hatch is WIN_PD_OVERRIDE_*. Setting only the POSIX variable is
        # why this test passed on Linux and failed on the Windows runner — and, as it turns out,
        # the Windows overrides were the *complete* pair while the POSIX side was one of three.
        "XDG_CONFIG_HOME": tmp_home,
        "XDG_DATA_HOME": tmp_home,
        "XDG_CACHE_HOME": tmp_home,
        "WIN_PD_OVERRIDE_APPDATA": tmp_home,
        "WIN_PD_OVERRIDE_LOCAL_APPDATA": tmp_home,
    }
    try:
        return subprocess.run(
            [sys.executable, "-c", source, *arguments],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as expired:
        # A silent timeout is indistinguishable from CI flakiness. Say what actually happened.
        raise AssertionError(
            "the application never exited within 120s. It either never showed a window or "
            f"never processed the queued quit.\nstdout: {expired.stdout!r}\n"
            f"stderr: {expired.stderr!r}"
        ) from expired


#: Emitted by the `offscreen` and `minimal` platform plugins when a window carrying a menu bar
#: is shown — neither implements `propagateSizeHints()`. Verified on 2026-07-25 to be an
#: artifact of those plugins and not of this application: the identical launch under a real
#: Wayland session exits zero with a completely empty stderr, and a bare `QMainWindow` with a
#: menu bar reproduces it under `offscreen` with no project code involved.
#:
#: Allowlisted by exact match, deliberately. Asserting "no *unexpected* stderr" keeps the
#: criterion meaningful; relaxing it to "ignore warnings" would retire the check entirely.
PLUGIN_NOISE = frozenset({"This plugin does not support propagateSizeHints()"})


def unexpected_stderr(stderr: str) -> list[str]:
    return [
        line for line in stderr.splitlines() if line.strip() and line.strip() not in PLUGIN_NOISE
    ]


def test_application_launches_and_exits_cleanly(tmp_path: pytest.TempPathFactory) -> None:
    """Zero exit code and no Qt warnings — the `T-007` criterion, on the real path."""
    result = run_headless(LAUNCH_AND_QUIT, str(tmp_path))
    assert result.returncode == 0, f"exit {result.returncode}\nstderr: {result.stderr}"
    # Asserted, not assumed: a quit that never fired would otherwise surface as an opaque
    # subprocess timeout, which reads like infrastructure flakiness rather than a defect.
    assert "WINDOW-SHOWN" in result.stdout, "the window never reached showEvent"
    assert "QUIT-REQUESTED" in result.stdout, "the window appeared but the quit never fired"
    assert result.stdout.index("WINDOW-SHOWN") < result.stdout.index("QUIT-REQUESTED"), (
        "the quit was processed before the window was shown, so show() did not precede exec()"
    )
    assert unexpected_stderr(result.stderr) == [], (
        f"Qt wrote something unexpected to stderr during a clean run:\n{result.stderr}"
    )


def test_launch_writes_geometry_on_exit(tmp_path: pytest.TempPathFactory) -> None:
    """A real launch/quit cycle must leave a geometry file behind, not just an in-process close."""
    result = run_headless(LAUNCH_AND_QUIT, str(tmp_path))
    assert result.returncode == 0, result.stderr
    written = list(map(str, __import__("pathlib").Path(tmp_path).rglob("window.toml")))
    assert written, "closing the real application must persist window geometry"


def test_unknown_arguments_exit_nonzero_with_usage(tmp_path: pytest.TempPathFactory) -> None:
    result = run_headless(
        "import sys\nfrom tracks_and_trails.app import run\n"
        "sys.exit(run(['tracks-and-trails', '--nonsense']))",
        str(tmp_path),
    )
    assert result.returncode == 2
    assert "usage:" in result.stdout
    assert result.stderr == ""


def test_help_exits_zero_without_a_display(tmp_path: pytest.TempPathFactory) -> None:
    """`--help` must not need Qt: it is the one thing a user runs when the GUI will not start."""
    source = "import sys\nfrom tracks_and_trails.app import run\nsys.exit(run(['t', '--help']))"
    result = subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={**os.environ, "QT_QPA_PLATFORM": "definitely-not-a-real-platform-plugin"},
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout


# --- T-282: the debug level, reachable without editing code -----------------------------------


def _cli(argument: str, tmp_path: object) -> subprocess.CompletedProcess[str]:
    """Run one argument through `run()` without a display, the way `--help` is exercised above."""
    source = (
        "import sys\nfrom tracks_and_trails.app import run\n"
        f"sys.exit(run(['tracks-and-trails', {argument!r}]))"
    )
    return subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={**os.environ, "QT_QPA_PLATFORM": "definitely-not-a-real-platform-plugin"},
    )


#: `LAUNCH_AND_QUIT`, but the arguments come from the command line so a level can be handed in.
#: The application log is read back afterwards, from the redirected cache root `run_headless` sets.
LAUNCH_AND_QUIT_WITH_ARGS = LAUNCH_AND_QUIT.replace(
    'sys.exit(run(["tracks-and-trails"]))',
    'sys.exit(run(["tracks-and-trails", *sys.argv[1:]]))',
)


@pytest.mark.parametrize(
    ("argument", "expected_level"),
    [
        pytest.param("--log-level=DEBUG", "DEBUG", id="the level that was asked for"),
        pytest.param(None, "INFO", id="the default, with no flag at all"),
    ],
)
def test_a_real_launch_configures_the_level_it_was_given(
    tmp_path: pytest.TempPathFactory, argument: str | None, expected_level: str
) -> None:
    """`T282-R3`: nothing invoked `run()` with a *valid* level, so the composition was unguarded.

    The launch tests covered `--help` and two rejections; the logging tests called
    `configure_logging(level=…)` directly. **Replacing `configure_logging(level=level)` with
    `configure_logging()` therefore left every one of them green** — the flag was parsed, validated,
    and then had no proven effect.

    This drives the real auto-quit launch and reads the application log it wrote, so the parse and
    the configuration are joined. **Both arms**, because asserting only `DEBUG` would pass against
    a build that ignored the flag and always ran at `DEBUG`.
    """
    home = tmp_path if argument is None else Path(str(tmp_path)) / expected_level
    result = run_headless(
        LAUNCH_AND_QUIT_WITH_ARGS, str(home), *([] if argument is None else [argument])
    )

    assert result.returncode == 0, f"exit {result.returncode}\nstderr: {result.stderr}"
    logs = list(Path(str(home)).rglob("tracks-and-trails.log"))
    assert logs, f"the launch wrote no application log under {home}"
    written = logs[0].read_text(encoding="utf-8")

    assert f"logging at {expected_level}" in written, (
        f"a launch with {argument!r} configured something other than {expected_level}: "
        f"{written.splitlines()[:3]}"
    )


def test_help_names_the_log_level_flag_and_where_the_log_is(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """`T-282`'s last criterion: the point is that somebody other than the implementer can use it.

    A flag nothing documents is an edit to the source by another route, and a flag that raises the
    volume of a file nobody can find is a diagnostic only its author can read — so `--help` carries
    both the flag and the resolved log path.
    """
    result = _cli("--help", tmp_path)

    assert result.returncode == 0, result.stderr
    assert "--log-level=LEVEL" in result.stdout, "the flag is not documented where --help looks"
    for name in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        assert name in result.stdout, f"--help does not name the {name} level"
    assert "tracks-and-trails.log" in result.stdout, "--help does not say where the log is"


@pytest.mark.parametrize(
    "argument",
    [
        pytest.param("--log-levels=DEBUG", id="a plural lookalike"),
        pytest.param("--log-level-extra=DEBUG", id="a longer lookalike"),
        pytest.param("--log-levelDEBUG", id="the value run into the flag"),
    ],
)
def test_a_lookalike_option_is_rejected_as_unknown(
    tmp_path: pytest.TempPathFactory, argument: str
) -> None:
    """`T282-R1`: a parser that runs before the unknown-argument check must not widen what is known.

    `startswith("--log-level")` matched all three of these. They are **misspellings, not spellings
    `--help` advertises**, and the catch-all would have rejected every one — but the new parser
    consumed them first, resolved a level from the text after `=`, and launched the application.
    Matching only the exact token and the exact `--log-level=` prefix hands them back.
    """
    result = _cli(argument, tmp_path)

    assert result.returncode == 2, f"{argument} was accepted: {result.stdout!r}"
    assert "usage:" in result.stdout, "the unknown-argument path did not print usage"
    assert "log level" not in result.stderr, (
        f"{argument} was treated as the log-level flag rather than as an unknown option: "
        f"{result.stderr!r}"
    )


@pytest.mark.parametrize(
    ("argument", "expected"),
    [
        pytest.param("--log-level=chatty", "unknown log level", id="a level that does not exist"),
        pytest.param("--log-level", "needs a value", id="the flag with no value"),
    ],
)
def test_a_bad_log_level_is_refused_rather_than_defaulted(
    tmp_path: pytest.TempPathFactory, argument: str, expected: str
) -> None:
    """**Refused, not defaulted**, which is the whole reason this is worth a test.

    Falling back to `INFO` when somebody asked for `DEBUG` produces a log missing exactly what they
    turned it on to see, and they would have no way to know. The complaint goes to stderr so it is
    not mistaken for the usage text it precedes.
    """
    result = _cli(argument, tmp_path)

    assert result.returncode == 2, f"a bad level was accepted: {result.stdout!r}"
    assert expected in result.stderr, f"the complaint does not say why: {result.stderr!r}"
    assert "usage:" in result.stdout


# --- T321-R1: the download probe, which is how a clean machine gets a real download ------------


def test_the_download_probe_is_dispatched_without_a_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """`--download-probe` alone means *the probe's own URL*, not an empty one.

    Dispatched in-process rather than through a subprocess because the point is the argument
    handling: the probe itself reaches the network and is run for release evidence, not here.
    """
    from tracks_and_trails import _freeze_probe
    from tracks_and_trails.app import run as run_app

    asked: list[str | None] = []
    monkeypatch.setattr(
        _freeze_probe, "run_download_probe", lambda url=None: (asked.append(url), 0)[1]
    )
    assert run_app(["tracks-and-trails", "--download-probe"]) == 0
    assert asked == [None]


def test_the_download_probe_takes_a_url_in_the_same_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`=URL`, the rule `--log-level` already follows.

    One token cannot be half-consumed, so a missing value is a bad value rather than the next
    flag being eaten — which is how `--log-level --version` would have turned `--version` into a
    level name.
    """
    from tracks_and_trails import _freeze_probe
    from tracks_and_trails.app import run as run_app

    asked: list[str | None] = []
    monkeypatch.setattr(
        _freeze_probe, "run_download_probe", lambda url=None: (asked.append(url), 0)[1]
    )
    assert run_app(["tracks-and-trails", "--download-probe=https://example.invalid/x.mp4"]) == 0
    assert asked == ["https://example.invalid/x.mp4"]


@pytest.mark.parametrize("misspelling", ["--download-probes", "--download-probe-url", "--download"])
def test_a_near_miss_is_rejected_rather_than_consumed(
    misspelling: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The defect `T282-R1` found in `--log-level`, not repeated here.

    `startswith("--download-probe")` would also match `--download-probes` — a misspelling the
    unknown-argument check would have caught, consumed instead and silently run the probe. A
    parser that runs before that check must not widen what counts as known.
    """
    from tracks_and_trails import _freeze_probe
    from tracks_and_trails.app import run as run_app

    def refuse(url: str | None = None) -> int:
        raise AssertionError(f"{misspelling} reached the probe with {url!r}")

    monkeypatch.setattr(_freeze_probe, "run_download_probe", refuse)
    assert run_app(["tracks-and-trails", misspelling]) == 2


def test_the_probe_is_listed_in_the_usage_text() -> None:
    """A probe nobody can discover is a probe nobody runs — and this one is release evidence."""
    from tracks_and_trails.app import _usage

    assert "--download-probe" in _usage()
