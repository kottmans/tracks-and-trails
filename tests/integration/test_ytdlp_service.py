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
import multiprocessing.context as mp_context
import threading
import time
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any

import pytest
from PySide6.QtWidgets import QApplication

from tracks_and_trails.downloader import process_tree
from tracks_and_trails.downloader import ytdlp_service as service_module
from tracks_and_trails.downloader.cancellation import OperationCancelledError
from tracks_and_trails.downloader.environment import (
    BASELINE_YTDLP_VERSION,
    normalise_version,
)
from tracks_and_trails.downloader.ytdlp_service import (
    Resolution,
    ResolutionUnavailableError,
    UpdateError,
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


def test_a_resolution_wait_stops_when_the_pool_is_cancelled(tmp_path: Path) -> None:
    """The ninety-second read could not notice a shutdown; the sliced one can (`T289-R21`).

    The whole of `resolve_in_a_child` is waiting, and one blocking `Queue.get` for the full timeout
    is a stretch of it in which nothing can be asked. The child here never answers, so the only
    thing that can end this call early is the checkpoint between slices — and the generous timeout
    is what makes that unambiguous: a run that ignored the cancellation would sit here for ninety
    seconds.

    **The flag turns true after several slices, not at once**, so the checkpoint being exercised is
    one inside the wait rather than the first one before it.
    """
    polls = 0

    def cancelled() -> bool:
        nonlocal polls
        polls += 1
        return polls > 3

    started = time.monotonic()
    with pytest.raises(OperationCancelledError, match="closing"):
        resolve_in_a_child(
            tmp_path,
            entry_point=_says_nothing,
            timeout=90.0,
            cancelled=cancelled,
        )
    elapsed = time.monotonic() - started

    assert polls > 3, "the wait was never re-asked, so nothing about slicing was proved"
    assert elapsed < 30.0, (
        f"the cancelled wait took {elapsed:.1f} s against a 90 s timeout; it was not the "
        "cancellation that ended it"
    )


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


def test_a_containment_refusal_reaches_the_user_with_its_reason(
    qapp: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T258-R9`, `T-263`: the refusal is only useful if the sentence survives the trip.

    `resolve_in_a_child` spawns through `process_tree.start_contained`, which raises
    `ContainmentUnavailableError` rather than starting a child the application cannot guarantee it
    can reap. That exception used to travel as itself, and `_Task.run`'s broad branch — which
    exists so nothing escapes onto a pool thread — reduced it to *"The operation could not be
    completed (ContainmentUnavailableError)."* The screen then said something had gone wrong and
    nothing about what, for a failure whose whole value is naming the boundary that failed.

    So the resolution path translates it into `ResolutionUnavailableError`, which the service
    already knows how to report verbatim. **Both halves are asserted here**: the reason arrives,
    and no child was started — a message that arrives after a child was spawned anyway would be
    the fail-open defect with better prose.
    """
    started: list[str] = []

    def counted(self: Any) -> None:
        started.append(type(self).__name__)

    # The class a spawn context actually constructs (`T258-R7`). Patching
    # `multiprocessing.context.Process` instead would land on a class nothing here uses.
    monkeypatch.setattr(mp_context.SpawnProcess, "start", counted)
    monkeypatch.setattr(process_tree, "contain_this_application", lambda: False)
    monkeypatch.setattr(process_tree, "application_containment_error", "probe: forced failure")

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

    assert not started, (
        f"a child was started while the application was uncontained: {started}. The refusal has "
        "to happen before the process exists, which is the whole order `start_contained` keeps."
    )
    assert not seen, f"a resolution was delivered by a refused spawn: {seen}"
    assert problems, "the refusal reached the user as nothing at all"
    assert "probe: forced failure" in problems[0], (
        "the containment reason did not survive the trip to the user. Got: "
        f"{problems[0]!r} — which is the broad branch reporting a type instead of the sentence."
    )


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


class RecordingExclusion:
    """A stand-in for whatever owns the workers, recording the hold's **lifetime** (`T198-R3`).

    Not a manager: what these tests are about is when the service takes the hold and when it
    gives it back, which is a claim about this class and not about queues.
    `test_composition.py`'s start-during-update regression drives the real manager, and
    `test_manager.py` proves the hold actually stops a start.
    """

    def __init__(self, *, grants: bool = True) -> None:
        self.grants = grants
        self.held = False
        self.events: list[str] = []

    def hold_worker_starts(self, reason: str) -> bool:
        self.events.append(f"hold:{reason}")
        if not self.grants:
            return False
        assert not self.held, "the hold was taken twice; a second holder would release the first"
        self.held = True
        return True

    def release_worker_starts(self) -> None:
        self.events.append("release")
        self.held = False


def _settles(finished: list[Any], problems: list[str]) -> bool:
    """Spin the loop until the service has ended its operation one way or the other."""
    deadline = time.monotonic() + 30.0
    while not finished and not problems and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    return bool(finished or problems)


def test_an_install_is_refused_while_workers_could_still_be_using_the_tree(
    qapp: Any, tmp_path: Path
) -> None:
    """**`T198-R3`.** Keeping a running worker's code tree stable is a correctness requirement.

    The first version of this reasoned from `_swap_into_place` failing on Windows when the
    directory is held open — and that is not a gate. Python does not keep every imported source
    file open, and on POSIX the rename **succeeds by design**, so a worker that has already
    imported `yt_dlp` resolves its later lazy imports (yt-dlp loads extractors on demand) from
    whatever now sits at that path. A revert makes that a missing import instead of a mixed one.

    So the guard is a refusal, not a rename that might fail — and a refusal to *hold*, not an
    answer to a question asked once.
    """
    exclusion = RecordingExclusion(grants=False)
    service = YtdlpService(
        directory=tmp_path / "ytdlp",
        entry_point=_reports_a_version,
        exclusion=exclusion,
    )
    problems: list[str] = []
    service.failed.connect(problems.append)

    service.install_latest_version()

    assert problems and "Stop the queue" in problems[0]
    assert service.busy is False, "a refused operation should not leave the screen disabled"
    assert exclusion.events == ["hold:installing yt-dlp"], (
        f"a hold that was never granted was released anyway: {exclusion.events}"
    )


def test_a_revert_is_refused_while_workers_could_still_be_using_the_tree(
    qapp: Any, tmp_path: Path
) -> None:
    """Reverting *removes* the tree, which is the worse half of `T198-R3`."""
    directory = tmp_path / "ytdlp"
    (directory / "yt_dlp").mkdir(parents=True)
    service = YtdlpService(
        directory=directory,
        entry_point=_reports_a_version,
        exclusion=RecordingExclusion(grants=False),
    )
    problems: list[str] = []
    service.failed.connect(problems.append)

    service.revert()

    assert problems and "Stop the queue" in problems[0]
    assert (directory / "yt_dlp").is_dir(), "the tree was removed underneath a running worker"


def test_the_hold_is_asked_for_again_rather_than_remembered(qapp: Any, tmp_path: Path) -> None:
    """A queue that was idle when the screen opened is not one that is idle when it is pressed."""
    exclusion = RecordingExclusion(grants=False)
    service = YtdlpService(
        directory=tmp_path / "ytdlp", entry_point=_reports_a_version, exclusion=exclusion
    )
    problems: list[str] = []
    finished: list[Any] = []
    service.failed.connect(problems.append)
    service.reported.connect(finished.append)

    service.revert()
    assert problems, "the first attempt should have been refused"

    exclusion.grants = True
    service.revert()

    assert _settles(finished, problems[1:]), "the second attempt never settled"
    assert finished, f"the second attempt was refused after the queue went idle: {problems}"


def test_the_workers_are_held_for_the_whole_operation_and_handed_back_at_its_end(
    qapp: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**The finding, stated as an interval rather than an instant** (`T198-R3` re-review).

    The previous correction asked a `workers_active()` predicate once, on the GUI thread, and
    then submitted the real work to the pool — so the index lookup, the download, the extraction
    and the swap all ran with the queue live behind them. What is asserted here is that the tree
    is still held **while the operation's own body is executing**, which is the window a start
    would land in, and released only once the whole thing — including the re-resolution that
    follows it — has finished.

    The observation is taken inside the patched operation, on the pool thread, because that is
    the only place that can distinguish "held around the call" from "held for the operation".
    """
    exclusion = RecordingExclusion()
    during: list[bool] = []

    def slow_revert(directory: Path) -> bool:
        during.append(exclusion.held)
        return True

    monkeypatch.setattr(service_module, "revert_to_baseline", slow_revert)
    service = YtdlpService(
        directory=tmp_path / "ytdlp", entry_point=_reports_a_version, exclusion=exclusion
    )
    problems: list[str] = []
    finished: list[Any] = []
    service.failed.connect(problems.append)
    service.reported.connect(finished.append)

    service.revert()
    assert exclusion.held, "the hold was not taken before the work was scheduled"

    assert _settles(finished, problems), "the operation never settled"
    assert not problems, f"the operation failed instead: {problems}"
    assert during == [True], (
        "the tree was not held while the operation ran; a worker starting here would import "
        "from a directory being replaced"
    )
    assert exclusion.events == ["hold:reverting yt-dlp", "release"]
    assert not exclusion.held, "the workers were never handed back"


def test_an_operation_that_fails_hands_the_workers_back(
    qapp: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A queue that can never start again is a worse defect than the one the hold prevents.

    Every escape from `_Task.run` arrives at one place, and it is the same place a success
    arrives at, so this holds for a failed download, a bad digest and an unwritable directory
    alike.
    """
    exclusion = RecordingExclusion()

    def unusable(directory: Path) -> bool:
        raise UpdateError("the wheel could not be read")

    monkeypatch.setattr(service_module, "revert_to_baseline", unusable)
    service = YtdlpService(
        directory=tmp_path / "ytdlp", entry_point=_reports_a_version, exclusion=exclusion
    )
    problems: list[str] = []
    finished: list[Any] = []
    service.failed.connect(problems.append)
    service.reported.connect(finished.append)

    service.revert()
    assert _settles(finished, problems), "the failure never arrived"

    assert problems == ["the wheel could not be read"]
    assert exclusion.events == ["hold:reverting yt-dlp", "release"]
    assert not exclusion.held, "a failed operation left the queue unable to start anything"
    assert service.busy is False


def test_a_second_operation_cannot_release_the_first_ones_hold(
    qapp: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The busy check comes **before** the hold, and this is what that ordering is for.

    A revert refused while an install is running must not hand back the workers the install is
    relying on. Ordered the other way round, the refusal would release a hold it never took and
    the install would finish its swap against a queue that had started again.
    """
    exclusion = RecordingExclusion()
    let_it_finish = threading.Event()

    def waits(directory: Path) -> bool:
        assert let_it_finish.wait(timeout=30.0), "the test never released the blocked operation"
        return True

    monkeypatch.setattr(service_module, "revert_to_baseline", waits)
    service = YtdlpService(
        directory=tmp_path / "ytdlp", entry_point=_reports_a_version, exclusion=exclusion
    )
    problems: list[str] = []
    finished: list[Any] = []
    service.failed.connect(problems.append)
    service.reported.connect(finished.append)

    try:
        service.revert()
        service.revert()

        assert problems == ["Another yt-dlp operation is still running."]
        assert exclusion.held, "the refused second operation gave away the first one's hold"
        assert exclusion.events == ["hold:reverting yt-dlp"]
    finally:
        let_it_finish.set()

    assert _settles(finished, problems[1:]), "the first operation never finished"
    assert not exclusion.held, "the first operation kept the workers after finishing"


def test_a_version_check_never_holds_the_workers(qapp: Any, tmp_path: Path) -> None:
    """Reading is not writing. `refresh` spawns a child that imports; it changes no tree, so a
    running queue is no reason to refuse the one thing `REQ-025` promises is always shown — and
    no reason to stop the queue starting anything while it is answered."""
    exclusion = RecordingExclusion(grants=False)
    service = YtdlpService(
        directory=tmp_path / "ytdlp",
        entry_point=_reports_a_version,
        exclusion=exclusion,
    )
    problems: list[str] = []
    finished: list[Any] = []
    service.failed.connect(problems.append)
    service.reported.connect(finished.append)

    service.refresh()

    assert _settles(finished, problems), "the version check never settled"
    assert not problems, f"a read-only version check was refused: {problems}"
    assert finished
    assert exclusion.events == [], "a version check held the workers"
