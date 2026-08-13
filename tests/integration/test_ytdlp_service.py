"""`T-198`: the version a user is shown comes from a worker's import, and an update changes it.

**These spawn real child processes and import real yt-dlp**, because that is the only thing that
can answer the question the task asks. The first criterion says the reported version is *"the
version the worker actually imports — read from the running environment, not from a pinned
constant or a packaging manifest"*, and every cheaper test would assert one of the things it
forbids.

`test_installing_then_reverting_moves_the_reported_version_and_moves_it_back` is the plan's exit
criterion end to end: *"Updating yt-dlp in-app changes the reported version and reverting restores
the baseline."* It installs a wheel built in the test rather than one fetched from PyPI — the
network belongs to `tests/unit/test_ytdlp_update.py`'s injected opener, and what is being proved
here is the *resolution*, not the download.
"""

import hashlib
import io
import json
import time
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any

import pytest
from PySide6.QtWidgets import QApplication

from tracks_and_trails.downloader.environment import (
    BASELINE_YTDLP_VERSION,
    normalise_version,
)
from tracks_and_trails.downloader.ytdlp_service import (
    Resolution,
    ResolutionUnavailableError,
    YtdlpService,
    resolve_in_a_child,
)
from tracks_and_trails.downloader.ytdlp_update import (
    PYPI_INDEX,
    install_latest,
    revert_to_baseline,
)


def _says_nothing(queue: Any, *, user_ytdlp_directory: Path | None = None) -> None:
    """A child that starts, reports nothing and exits. Module-level so `spawn` can pickle it."""
    return None


#: A version no real yt-dlp will ever report, so a test asserting it cannot be satisfied by the
#: baseline leaking through.
INSTALLED_VERSION = "3000.1.1"


def _importable_ytdlp(version: str) -> dict[str, str]:
    """The minimum a copy must contain for `worker._import_ytdlp` to accept it.

    `__init__` imports `.version` because that is how the real package exposes
    `yt_dlp.version.__version__` — a copy without it imports and then fails on the attribute,
    which is a *different* test's subject (`test_worker.py`'s broken-copy shapes).
    """
    return {
        "yt_dlp/__init__.py": "from . import version\n__version__ = version.__version__\n",
        "yt_dlp/version.py": f"__version__ = {version!r}\nRELEASE_GIT_HEAD = None\n",
    }


def _wheel(version: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in _importable_ytdlp(version).items():
            archive.writestr(name, text)
        archive.writestr(f"yt_dlp-{version}.dist-info/METADATA", f"Version: {version}\n")
    return buffer.getvalue()


def _opener_serving(version: str) -> Any:
    """An opener whose index and wheel agree, so `install_latest` runs its ordinary path."""
    payload = _wheel(version)
    url = f"https://files.pythonhosted.org/yt_dlp-{version}-py3-none-any.whl"
    document = {
        "info": {"version": version},
        "urls": [
            {
                "packagetype": "bdist_wheel",
                "filename": f"yt_dlp-{version}-py3-none-any.whl",
                "url": url,
                "digests": {"sha256": hashlib.sha256(payload).hexdigest()},
            }
        ],
    }
    responses = {PYPI_INDEX: json.dumps(document).encode(), url: payload}

    @contextmanager
    def opener(requested: str) -> Iterator[IO[bytes]]:
        yield io.BytesIO(responses[requested])

    return opener


def test_the_reported_version_is_the_baseline_a_child_actually_imports(tmp_path: Path) -> None:
    """Criterion one, with nothing installed: a child imports and says what it got.

    Asserted through `normalise_version` because the pin is written `2026.7.4` and the package
    reports `2026.07.04` — the same release, and a string comparison would fail a correct tree
    (`T033-R1`).
    """
    resolution = resolve_in_a_child(tmp_path / "absent")

    assert isinstance(resolution, Resolution)
    assert normalise_version(resolution.version) == normalise_version(BASELINE_YTDLP_VERSION)
    assert "baseline" in resolution.source
    assert resolution.is_user_managed is False


def test_a_user_copy_is_what_the_child_imports_and_reports(tmp_path: Path) -> None:
    """The mechanism the whole task rests on: what is in that directory is what runs.

    If this were not true, an update could land, report a new version, and change nothing about
    the download that followed — the failure `T-198` calls the worst outcome available, because it
    looks like it worked.
    """
    directory = tmp_path / "ytdlp"
    (directory / "yt_dlp").mkdir(parents=True)
    for name, text in _importable_ytdlp(INSTALLED_VERSION).items():
        (directory / name).write_text(text)

    resolution = resolve_in_a_child(directory)

    assert resolution.version == INSTALLED_VERSION
    assert resolution.is_user_managed is True


def test_installing_then_reverting_moves_the_reported_version_and_moves_it_back(
    tmp_path: Path,
) -> None:
    """**The plan's exit criterion, in one test.**

    Three readings, each from its own spawned child: the baseline before, the installed version
    after, and the baseline again after reverting. Nothing here reads a `.dist-info` name or the
    installer's own return value to decide what is in use — each assertion is a fresh import.
    """
    directory = tmp_path / "ytdlp"

    before = resolve_in_a_child(directory)
    assert normalise_version(before.version) == normalise_version(BASELINE_YTDLP_VERSION)

    installed = install_latest(directory, _opener_serving(INSTALLED_VERSION))
    assert installed.version == INSTALLED_VERSION

    after = resolve_in_a_child(directory)
    assert after.version == INSTALLED_VERSION, "the install did not change what a worker imports"
    assert after.is_user_managed is True

    assert revert_to_baseline(directory) is True

    restored = resolve_in_a_child(directory)
    assert normalise_version(restored.version) == normalise_version(BASELINE_YTDLP_VERSION)
    assert restored.is_user_managed is False


def test_a_broken_installed_copy_falls_back_and_the_rejection_is_reported(tmp_path: Path) -> None:
    """`ARCHITECTURE.md` §6: a rejected override is reported, never silently ignored.

    A user who installed a copy that does not import must not be left reading the baseline's
    version with nothing saying why their update had no effect.
    """
    directory = tmp_path / "ytdlp"
    (directory / "yt_dlp").mkdir(parents=True)
    (directory / "yt_dlp" / "__init__.py").write_text("raise ImportError('deliberately broken')\n")

    resolution = resolve_in_a_child(directory)

    assert normalise_version(resolution.version) == normalise_version(BASELINE_YTDLP_VERSION)
    assert resolution.is_user_managed is False
    assert resolution.rejected, "the rejected copy was not reported"


def test_no_reported_field_carries_a_filesystem_path(tmp_path: Path) -> None:
    """`NFR-007`, on the surface a settings screen renders directly.

    The user directory sits under the user's home, so a source or a rejection reason quoting it
    puts a username into anything the screen is copied into.
    """
    directory = tmp_path / "ytdlp"
    (directory / "yt_dlp").mkdir(parents=True)
    (directory / "yt_dlp" / "__init__.py").write_text("raise ImportError('deliberately broken')\n")

    resolution = resolve_in_a_child(directory)

    rendered = " ".join((resolution.version, resolution.source, *resolution.rejected))
    assert str(directory) not in rendered
    assert str(tmp_path) not in rendered


def test_a_child_that_never_answers_is_given_up_on(tmp_path: Path) -> None:
    """The screen must not wait forever on a child that hung importing an extractor.

    Driven with an entry point that puts nothing on the queue, which is what a child killed
    before it could report looks like from here.

    **The entry point is module-level because `spawn` pickles it.** A locally defined one raised
    at `start()`, and the first version of this test then failed on *"can only join a started
    process"* — a real defect it found in the service's own cleanup, which is now guarded.
    """
    with pytest.raises(ResolutionUnavailableError, match="took too long"):
        resolve_in_a_child(tmp_path, entry_point=_says_nothing, timeout=1.0)


def _reports_a_version(queue: Any, *, user_ytdlp_directory: Path | None = None) -> None:
    """A child that reports one version and exits. Module-level so `spawn` can pickle it."""
    from tracks_and_trails.downloader.protocol import ResolutionReport, WorkerFinished

    queue.put(
        ResolutionReport(
            job_id="ytdlp-resolution",
            ytdlp_version=INSTALLED_VERSION,
            ytdlp_source="user-managed copy (OPS-002)",
        )
    )
    queue.put(WorkerFinished(job_id="ytdlp-resolution", exit_code=0))


def test_the_service_delivers_a_resolution_through_its_signal(qapp: Any, tmp_path: Path) -> None:
    """**The async path, and the defect it had.**

    `refresh()` runs on a `QThreadPool`, and the first version passed the runnable straight to
    `start()` without keeping a reference. `QThreadPool` owns the C++ runnable but not the Python
    object, so the task — and the parentless `_Sink` it emits through — could be collected while
    still running, raising `RuntimeError: Signal source has been deleted` from a pool thread with
    no handler. The composition regression found it; this drives it directly.

    Nothing here imports yt-dlp: the child is injected, which is what makes the pool path
    testable in under a second instead of not at all.
    """
    service = YtdlpService(directory=tmp_path / "ytdlp", entry_point=_reports_a_version)
    seen: list[Any] = []
    problems: list[str] = []
    service.reported.connect(seen.append)
    service.failed.connect(problems.append)

    service.refresh()

    deadline = time.monotonic() + 30.0
    while not seen and not problems and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)

    assert not problems, f"the service reported a failure instead: {problems}"
    assert seen, "the service never delivered a resolution"
    assert isinstance(seen[0], Resolution)
    assert seen[0].version == INSTALLED_VERSION
    assert service.busy is False, "the service stayed busy after finishing"


def test_a_second_operation_is_refused_while_one_is_running(qapp: Any, tmp_path: Path) -> None:
    """They write the same directory, so the guard belongs here and not only on the buttons.

    **The wait at the end is not politeness.** Returning while the first query's child is still
    running lets the service — and the sink its task emits through — be collected mid-flight,
    which reproduces the deleted-signal-source error this class was just fixed for, in a test that
    would otherwise report a pass while printing it.
    """
    service = YtdlpService(directory=tmp_path / "ytdlp", entry_point=_reports_a_version)
    problems: list[str] = []
    finished: list[Any] = []
    service.failed.connect(problems.append)
    service.reported.connect(finished.append)

    service.refresh()
    service.refresh()

    assert problems == ["Another yt-dlp operation is still running."]

    deadline = time.monotonic() + 30.0
    while not finished and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    assert finished, (
        "the first query never finished, so the second was refused for the wrong reason"
    )


def test_an_install_is_refused_while_workers_could_still_be_using_the_tree(
    qapp: Any, tmp_path: Path
) -> None:
    """**`T198-R3`.** Keeping a running worker's code tree stable is a correctness requirement.

    The first version of this reasoned from `_swap_into_place` failing on Windows when the
    directory is held open — and that is not a gate. Python does not keep every imported source
    file open, and on POSIX the rename **succeeds by design**, so a worker that has already
    imported `yt_dlp` resolves its later lazy imports (yt-dlp loads extractors on demand) from
    whatever now sits at that path. A revert makes that a missing import instead of a mixed one.

    So the guard is a refusal, not a rename that might fail.
    """
    service = YtdlpService(
        directory=tmp_path / "ytdlp",
        entry_point=_reports_a_version,
        workers_active=lambda: True,
    )
    problems: list[str] = []
    service.failed.connect(problems.append)

    service.install_latest_version()

    assert problems and "Stop the queue" in problems[0]
    assert service.busy is False, "a refused operation should not leave the screen disabled"


def test_a_revert_is_refused_while_workers_could_still_be_using_the_tree(
    qapp: Any, tmp_path: Path
) -> None:
    """Reverting *removes* the tree, which is the worse half of `T198-R3`."""
    directory = tmp_path / "ytdlp"
    (directory / "yt_dlp").mkdir(parents=True)
    service = YtdlpService(
        directory=directory, entry_point=_reports_a_version, workers_active=lambda: True
    )
    problems: list[str] = []
    service.failed.connect(problems.append)

    service.revert()

    assert problems and "Stop the queue" in problems[0]
    assert (directory / "yt_dlp").is_dir(), "the tree was removed underneath a running worker"


def test_the_guard_is_re_read_rather_than_cached(qapp: Any, tmp_path: Path) -> None:
    """A queue that was idle when the screen opened is not one that is idle when it is pressed."""
    active = {"value": True}
    service = YtdlpService(
        directory=tmp_path / "ytdlp",
        entry_point=_reports_a_version,
        workers_active=lambda: active["value"],
    )
    problems: list[str] = []
    finished: list[Any] = []
    service.failed.connect(problems.append)
    service.reported.connect(finished.append)

    service.revert()
    assert problems, "the first attempt should have been refused"

    active["value"] = False
    service.revert()

    deadline = time.monotonic() + 30.0
    while not finished and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    assert finished, "the second attempt was refused after the queue went idle"


def test_a_version_check_is_never_refused(qapp: Any, tmp_path: Path) -> None:
    """Reading is not writing. `refresh` spawns a child that imports; it changes no tree, so a
    running queue is no reason to refuse the one thing `REQ-025` promises is always shown."""
    service = YtdlpService(
        directory=tmp_path / "ytdlp",
        entry_point=_reports_a_version,
        workers_active=lambda: True,
    )
    problems: list[str] = []
    finished: list[Any] = []
    service.failed.connect(problems.append)
    service.reported.connect(finished.append)

    service.refresh()

    deadline = time.monotonic() + 30.0
    while not finished and not problems and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    assert not problems, f"a read-only version check was refused: {problems}"
    assert finished
