"""Phase 2's exit criteria, in executable form (`T-088`, the analogue of `T-037`).

Phase 1's criteria were met by tests written for other reasons, plus `T-037` for the two that had
no owner. Phase 2's are different in one specific way: **every one of them is about N**, and a
feature task proving itself for one job proves nothing about the pool. Three downloads at once,
a kill with a queue behind it, a limit lowered while workers are running, a shutdown with some
workers started and some not.

## What this file is careful about, learned the expensive way

**A kill is only evidence if something was alive to kill.** `T072-R1` failed twice here: once by
asserting against the same list the kill was handed, and once by counting *every* descendant — which
on `multiprocessing` includes the resource tracker, so a mutation that killed the application and
the tracker while deliberately sparing the real worker **passed in 1.38 s**. The worker set is
obtained independently, and the tracker is excluded by **being identified**, not by everything else
being allow-listed. Both helpers are imported from `test_end_to_end` rather than rewritten, because
a second copy of that reasoning is a second copy to get wrong.

**Downloads are paced so a survivor is still running when we look.** A clip that finishes in under a
second means a worker missed by the kill has exited naturally before any assertion runs, and the
check passes with no kill at all.

## What no test in this file covers

- **Windows.** These run on `ubuntu-latest` and on `windows-latest`; `STARBASE` is offline and
  `OPS-005`'s 2026-08-01 amendment puts the Windows gate on the hosted job. The **desktop** slice
  — a real interactive session — is not covered anywhere and stays with `T-026` and `T-040`.
- **Real network conditions.** The media server is localhost. Nothing here says anything about
  behaviour against a real host, a slow link, or an extractor that misbehaves.
- **`NFR-001`'s responsiveness as a human experiences it.** What is asserted is that the GUI thread
  keeps servicing events while three workers run — not that a person would call it smooth.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import suppress
from http.server import ThreadingHTTPServer
from pathlib import Path

import psutil
import pytest
from PySide6.QtWidgets import QApplication

from tests.integration.test_end_to_end import (
    CLIP_BYTES,
    REPO_ROOT,
    capture_the_doomed_tree,
    isolate_the_application,
    kill_the_application,
    media_handler,
    the_workers_that_must_die,
)
from tracks_and_trails.core.job_state import JobStatus
from tracks_and_trails.persistence import db
from tracks_and_trails.persistence.repositories import INTERRUPTED_ON_STARTUP, JobRepository


@pytest.fixture
def media_url() -> Iterator[Callable[..., str]]:
    """A localhost media URL per call. **Its own fixture, not `test_end_to_end`'s.**

    Importing a fixture by name works and makes this file's server the *other* file's, so a change
    to that one's pacing silently retunes these. The handler is shared because it is the thing
    worth having one of; the lifecycle is local because it is the thing worth owning.
    """
    servers: list[ThreadingHTTPServer] = []

    def serve(total_bytes: int = CLIP_BYTES, chunk_delay: float = 0.0) -> str:
        server = ThreadingHTTPServer(("127.0.0.1", 0), media_handler(total_bytes, chunk_delay))
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{server.server_address[1]}/clip.mp4"

    yield serve

    for server in servers:
        server.shutdown()
        server.server_close()


#: How many jobs the pool is asked to hold at once. Three because `NFR-001` and the phase's first
#: exit criterion both say three, not because three is a round number.
CONCURRENT = 3

#: Queued but deliberately **beyond** the limit, so some jobs have never started when the
#: application is killed or shut down. Criterion 5 is about workers that were never launched as
#: much as about ones that were.
QUEUED_BEYOND_LIMIT = 2


QUEUE_MANY_AND_WAIT = """
import os
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication

from tracks_and_trails import app as application

database, downloads, geometry, concurrency, *urls = sys.argv[1:]
qapp = QApplication([])
settings = Path(geometry).with_name("settings.toml")
settings.write_text("[queue]\\nconcurrency = " + concurrency + "\\n", encoding="utf-8")
composition = application.compose(
    qapp,
    database=Path(database),
    output_directory=Path(downloads),
    geometry_file=Path(geometry),
    settings_file=settings,
)
dialog = composition.window.open_add_dialog()
dialog._urls.setPlainText("\\n".join(urls))
names = [dialog._preset_choice.itemText(i) for i in range(dialog._preset_choice.count())]
dialog._preset_choice.setCurrentIndex(names.index("Best video available"))
dialog.add_to_queue()
while len(dialog.queued_job_ids) < len(urls):
    qapp.processEvents()
job_ids = list(dialog.queued_job_ids)
dialog.close()
# **Started explicitly, and the refusal beyond the limit is caught rather than fatal.**
# `DownloadManager.start()` raises when the pool is full; the internal path parks instead. That
# asymmetry is deliberate on the manager's side and it is *also* why this loop cannot simply
# start everything. See `T-115` — the application offers no route that drains a queue at all.
started = []
for job_id in job_ids:
    try:
        composition.manager.start(job_id)
        started.append(job_id)
    except RuntimeError:
        pass
# The application's own pid, not the launcher's: under a Windows venv `Popen` returns the
# launcher and a count beneath it cannot tell a worker-less tree from a healthy one (`T072-R1`).
print(os.getpid(), " ".join(job_ids), flush=True)
sys.exit(qapp.exec())
"""


def launch(
    script: str,
    *,
    database: Path,
    downloads: Path,
    geometry: Path,
    concurrency: int,
    urls: list[str],
) -> tuple[subprocess.Popen[str], int, list[str]]:
    """Start a real application in another interpreter and read its startup handshake."""
    downloads.mkdir(exist_ok=True)
    environment = dict(os.environ, PYTHONPATH=str(REPO_ROOT / "src"), QT_QPA_PLATFORM="offscreen")
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            script,
            str(database),
            str(downloads),
            str(geometry),
            str(concurrency),
            *urls,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
        **isolate_the_application(),
    )
    assert process.stdout is not None
    handshake = process.stdout.readline().strip()
    if not handshake:
        # `T-062`: a failure on a machine nobody can reach has to say what happened. An empty
        # handshake means the child reached EOF, which means it died — and its stderr is the only
        # place the reason exists.
        process.kill()
        _, errors = process.communicate(timeout=30)
        raise AssertionError(
            "the application never queued anything; it exited with "
            f"{process.returncode}. Its stderr:\n{errors[-3000:]}"
        )
    reported_pid, _, ids = handshake.partition(" ")
    job_ids = ids.split()
    assert job_ids, f"the handshake was not '<pid> <job ids...>': {handshake!r}"
    return process, int(reported_pid), job_ids


def statuses(database: Path, job_ids: list[str]) -> dict[str, JobStatus]:
    """Read every job's status from a **separate connection**.

    The application that owns the database is the one about to be killed, so its connection is not
    a thing this test may borrow.
    """
    reader = db.connect(database)
    try:
        repository = JobRepository(reader)
        found = {}
        for job_id in job_ids:
            job = repository.get(job_id)
            if job is not None:
                found[job_id] = job.status
        return found
    finally:
        reader.close()


def wait_until(predicate: Callable[[], bool], timeout: float = 120.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return False


def wait_for_workers(
    application_pid: int, count: int, timeout: float = 120.0
) -> list[psutil.Process]:
    """Wait until `count` **worker processes** exist, not until `count` rows say they do.

    **The rows lead the processes.** `start()` writes the transition to `PROBING` through the
    writer thread and the worker is spawned after, so there is a window in which three rows claim
    to be in flight and no process exists yet. Measured: at t=0.0 s three rows said `probing` with
    an empty process tree. Waiting on the rows made `the_workers_that_must_die` fire its own guard
    — correctly — and a kill test that raced the spawn would otherwise have been "fixed" by
    weakening that guard, which is exactly what `T072-R1` warns about.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            workers = the_workers_that_must_die(application_pid)
        except AssertionError, psutil.NoSuchProcess:
            workers = []
        if len(workers) >= count:
            return workers
        time.sleep(0.1)
    raise AssertionError(
        f"only {len(workers)} worker process(es) ever existed against {count} expected; a kill "
        "that reaches fewer processes than there are jobs says nothing about a pool"
    )


def running_count(database: Path, job_ids: list[str]) -> int:
    live = {JobStatus.PROBING, JobStatus.READY, JobStatus.RUNNING, JobStatus.POST_PROCESSING}
    return sum(1 for status in statuses(database, job_ids).values() if status in live)


# --- criterion 2: a hard kill mid-queue, and what the next start finds ------------------------


def test_a_hard_kill_mid_queue_restores_every_job_state_at_the_next_start(
    qapp: QApplication, tmp_path: Path, media_url: Callable[..., str]
) -> None:
    """**Exit criterion 2**, with a queue behind the kill rather than one job.

    Phase 1's version killed a single download. What is new is the plural: several workers in
    flight, several jobs queued and never started, and one `SIGKILL` with no handlers. Every row
    must come back describing something that is true — the in-flight ones recovered and offering a
    retry, the never-started ones still queued and untouched.

    **The never-started jobs are the half a single-job test cannot reach.** A recovery that swept
    every row would move them too, and a user would find downloads that had not begun reported as
    interrupted.

    *Does not cover:* the offer dialog, which is `T-082`'s and is tested at composition level; and
    resumption of partial bytes, which this phase does not do.
    """
    database = tmp_path / "queue.db"
    urls = [
        media_url(total_bytes=CLIP_BYTES, chunk_delay=0.5)
        for _ in range(CONCURRENT + QUEUED_BEYOND_LIMIT)
    ]
    process, application_pid, job_ids = launch(
        QUEUE_MANY_AND_WAIT,
        database=database,
        downloads=tmp_path / "downloads",
        geometry=tmp_path / "window.toml",
        concurrency=CONCURRENT,
        urls=urls,
    )
    try:
        # Wait on the **processes**, not on the rows: `start()` writes `PROBING` through the
        # writer thread and the worker is spawned after, so three rows can claim to be in flight
        # with an empty process tree. Measured at t=0.0 s.
        workers = wait_for_workers(application_pid, CONCURRENT)
        # And wait for the kill to land during a **download** rather than during a probe. Both are
        # "mid-queue" and `INTERRUPTED_ON_STARTUP` covers both, but a kill that always arrived
        # while three workers were still resolving URLs would never exercise the case a user
        # actually loses — bytes in flight.
        assert wait_until(
            lambda: any(
                status is JobStatus.RUNNING for status in statuses(database, job_ids).values()
            ),
            timeout=90,
        ), f"no job ever reached RUNNING; saw {statuses(database, job_ids)}"
        before = statuses(database, job_ids)
        doomed = capture_the_doomed_tree(process, application_pid)

        kill_the_application(process, doomed)
        _, alive = psutil.wait_procs(workers, timeout=30)
        assert not alive, f"{len(alive)} worker(s) outlived the kill: {[p.pid for p in alive]}"
    finally:
        process.kill()
        process.wait(timeout=30)

    # The next start is the application's own recovery, not this test's.
    recovered = JobRepository(db.connect(database)).recover_interrupted()
    after = statuses(database, job_ids)

    # **The same set the recovery uses**, not just `RUNNING`. A worker resolving a URL is as
    # interrupted as one writing bytes, and asserting only on `RUNNING` would make this test's
    # verdict depend on where in a session the kill happened to land.
    in_flight = [job_id for job_id, status in before.items() if status in INTERRUPTED_ON_STARTUP]
    assert in_flight, f"nothing was in flight at kill time: {before}"
    for job_id in in_flight:
        assert job_id in recovered, f"{job_id} was in flight and was not recovered"
        assert after[job_id] is JobStatus.FAILED

    never_started = [job_id for job_id, status in before.items() if status is JobStatus.QUEUED]
    assert never_started, (
        f"every job had started, so this says nothing about the ones that had not: {before}"
    )
    for job_id in never_started:
        assert job_id not in recovered, f"{job_id} had never started and was reported interrupted"
        assert after[job_id] is JobStatus.QUEUED


# --- criterion 5: no worker outlives application exit -----------------------------------------


def test_no_worker_outlives_a_hard_kill_with_a_full_pool(
    qapp: QApplication, tmp_path: Path, media_url: Callable[..., str]
) -> None:
    """**Exit criterion 5**, at `CONCURRENT` workers rather than one.

    `T-019` reaps the tree, `T-066` found that a virtualenv adds a process level nobody was
    testing, and `T-072` established that it is the worker's **own** parent-watchdog rather than
    the captured set that actually prevents orphans. With N workers the open question is whether
    that holds N times — including for a worker that was starting as the kill landed.

    The worker set is obtained **independently of what is killed**, and asserted non-empty before
    the kill: `T072-R1`'s two failed versions both looked exactly like checks.

    *Does not cover:* an `ffmpeg` grandchild, which these presets do not spawn; and Windows, where
    the same test runs on the hosted job under a different `kill_the_application`.
    """
    database = tmp_path / "queue.db"
    urls = [media_url(total_bytes=CLIP_BYTES, chunk_delay=0.5) for _ in range(CONCURRENT)]
    process, application_pid, _ = launch(
        QUEUE_MANY_AND_WAIT,
        database=database,
        downloads=tmp_path / "downloads",
        geometry=tmp_path / "window.toml",
        concurrency=CONCURRENT,
        urls=urls,
    )
    try:
        workers = wait_for_workers(application_pid, CONCURRENT)
        doomed = capture_the_doomed_tree(process, application_pid)

        kill_the_application(process, doomed)

        _, alive = psutil.wait_procs(workers, timeout=60)
        assert not alive, (
            f"{len(alive)} of {len(workers)} worker(s) outlived the application: "
            f"{[(p.pid, ' '.join(p.cmdline()[:3])) for p in alive]}"
        )
    finally:
        process.kill()
        process.wait(timeout=30)


# --- criterion 3: the limit is respected exactly ----------------------------------------------


def test_the_pool_never_exceeds_the_configured_limit(
    qapp: QApplication, tmp_path: Path, media_url: Callable[..., str]
) -> None:
    """**Exit criterion 3's first half**, sampled against a real application over its whole run.

    Asserted as *never exceeded* rather than *reached*, and sampled repeatedly rather than once:
    a limit checked at a single moment is satisfied by a pool that overshoots between samples.

    **Two counts are taken and both are held to the limit** — the rows the application thinks are
    in flight, and the worker processes that actually exist. They can disagree, and the second is
    the one that costs a user their bandwidth.

    *Does not cover:* raising the limit while running, which `T-078` covers; and the exact moment
    a slot is released, which is the manager's own tests.
    """
    database = tmp_path / "queue.db"
    urls = [
        media_url(total_bytes=CLIP_BYTES, chunk_delay=0.3)
        for _ in range(CONCURRENT + QUEUED_BEYOND_LIMIT)
    ]
    process, application_pid, job_ids = launch(
        QUEUE_MANY_AND_WAIT,
        database=database,
        downloads=tmp_path / "downloads",
        geometry=tmp_path / "window.toml",
        concurrency=CONCURRENT,
        urls=urls,
    )
    peak_rows = 0
    peak_workers = 0
    try:
        assert wait_until(lambda: running_count(database, job_ids) > 0), "nothing ever started"
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            peak_rows = max(peak_rows, running_count(database, job_ids))
            with suppress(AssertionError, psutil.NoSuchProcess):
                # Between jobs there is briefly no worker, which is not an overshoot.
                peak_workers = max(peak_workers, len(the_workers_that_must_die(application_pid)))
            if all(
                status in {JobStatus.COMPLETED, JobStatus.FAILED}
                for status in statuses(database, job_ids).values()
            ):
                break
            time.sleep(0.1)
    finally:
        process.kill()
        process.wait(timeout=30)

    assert peak_rows, "no job was ever observed in flight, so no limit was ever tested"
    assert peak_rows <= CONCURRENT, (
        f"{peak_rows} jobs were in flight at once against a limit of {CONCURRENT}"
    )
    assert peak_workers <= CONCURRENT, (
        f"{peak_workers} worker processes existed at once against a limit of {CONCURRENT}; the "
        "queue's own accounting agreed with the limit, so this is the pool and not the rows"
    )


# --- criterion 4: a second launch --------------------------------------------------------------


def test_a_second_launch_refuses_in_favour_of_the_running_instance(
    qapp: QApplication, tmp_path: Path, media_url: Callable[..., str]
) -> None:
    """**Exit criterion 4**, against a first instance that is genuinely busy.

    `T-087` proves the lock, including two launches racing, and passed on `windows-latest`. What
    this adds is the phase-level shape: the second launch arrives while the first has a **full
    pool**, which is when a guard implemented by polling or by a timeout would be most likely to
    let it through.

    *Does not cover:* attaching. `ARC-006` allows attach *or* refuse and this application refuses;
    a future attach channel would need its own test rather than this one relaxed.
    """
    database = tmp_path / "queue.db"
    urls = [media_url(total_bytes=CLIP_BYTES, chunk_delay=0.5) for _ in range(CONCURRENT)]
    process, _, job_ids = launch(
        QUEUE_MANY_AND_WAIT,
        database=database,
        downloads=tmp_path / "downloads",
        geometry=tmp_path / "window.toml",
        concurrency=CONCURRENT,
        urls=urls,
    )
    try:
        assert wait_until(lambda: running_count(database, job_ids) >= CONCURRENT), (
            f"the pool never filled; saw {statuses(database, job_ids)}"
        )

        environment = dict(
            os.environ, PYTHONPATH=str(REPO_ROOT / "src"), QT_QPA_PLATFORM="offscreen"
        )
        second = subprocess.run(
            [
                sys.executable,
                "-c",
                QUEUE_MANY_AND_WAIT,
                str(database),
                str(tmp_path / "downloads2"),
                str(tmp_path / "window2.toml"),
                str(CONCURRENT),
                urls[0],
            ],
            capture_output=True,
            text=True,
            env=environment,
            timeout=120,
        )

        assert second.returncode != 0, (
            "a second launch started against a database another instance is writing; that is the "
            "corruption ARC-006 exists to prevent, and it happened while the first pool was full"
        )
        message = (second.stderr + second.stdout).lower()
        assert "already" in message or "running" in message or "instance" in message, (
            f"the second launch refused without saying why, which a user cannot act on: "
            f"{second.stderr[-600:]}"
        )
    finally:
        process.kill()
        process.wait(timeout=30)


# --- criterion 1: three at once, and the UI still answering ------------------------------------


def test_three_downloads_progress_independently_while_the_ui_keeps_answering(
    qapp: QApplication, tmp_path: Path, media_url: Callable[..., str]
) -> None:
    """**Exit criterion 1**, observed from outside the application.

    Independence is asserted as **distinct progress**: three jobs whose written bytes differ from
    one another at some sampled moment. Three jobs that all report the same number are the shape a
    single shared counter produces, and it looks exactly like success on a fast machine.

    Interactivity is asserted as the application still **advancing its own state** while three
    workers run — the rows keep changing. A GUI thread blocked on a worker or on SQLite (`ARC-005`)
    stops producing transitions, and that is observable from another process.

    *Does not cover:* `NFR-001`'s responsiveness as a human perceives it. This says the event loop
    is being serviced, not that a person would call it smooth. `T-079`'s own tests assert the
    progress rendering; this asserts that three of them are genuinely three.
    """
    database = tmp_path / "queue.db"
    downloads = tmp_path / "downloads"
    urls = [media_url(total_bytes=CLIP_BYTES, chunk_delay=0.3) for _ in range(CONCURRENT)]
    process, _, job_ids = launch(
        QUEUE_MANY_AND_WAIT,
        database=database,
        downloads=downloads,
        geometry=tmp_path / "window.toml",
        concurrency=CONCURRENT,
        urls=urls,
    )
    transitions: list[dict[str, JobStatus]] = []
    try:
        assert wait_until(lambda: running_count(database, job_ids) >= CONCURRENT), (
            f"three downloads never ran at once; saw {statuses(database, job_ids)}"
        )

        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            snapshot = statuses(database, job_ids)
            if not transitions or snapshot != transitions[-1]:
                transitions.append(snapshot)
            if all(
                status in {JobStatus.COMPLETED, JobStatus.FAILED} for status in snapshot.values()
            ):
                break
            time.sleep(0.1)
    finally:
        process.kill()
        process.wait(timeout=30)

    final = statuses(database, job_ids)
    assert len(final) == CONCURRENT
    assert all(status is JobStatus.COMPLETED for status in final.values()), (
        f"not every concurrent download completed: {final}"
    )
    assert len(transitions) > 1, (
        "the application's state never changed while three workers ran, which is what a blocked "
        "GUI thread looks like from outside"
    )

    written = sorted(path.stat().st_size for path in downloads.glob("*") if path.is_file())
    assert len(written) == CONCURRENT, f"expected {CONCURRENT} files, found {written}"
    assert all(size == CLIP_BYTES for size in written), (
        f"three concurrent downloads did not each write the whole clip: {written}"
    )


# --- what proving the phase found: the queue does not drain -----------------------------------


def test_a_job_beyond_the_limit_never_starts_even_once_the_pool_empties() -> None:
    """**`T-115`. Recorded as an expected failure, because it is a real gap and not a quirk.**

    Measured 2026-08-01 against a real composed application, concurrency 3, five jobs queued:

    ```
      0.5s  probing  running  probing  queued  queued   (4 children)
      8.0s  completed completed completed queued queued (1 child)
      9.5s  completed completed completed queued queued (1 child)
    ```

    The three that started ran concurrently and completed. **The other two stayed `queued` with an
    empty pool**, and were still queued when the run ended.

    Reading the code says the same thing. `DownloadManager._fill_free_slots` drains `_waiting`,
    which is an **in-memory** list populated only when `_start_or_report` parks a job. The public
    `start()` *raises* when the pool is full rather than parking, and nothing anywhere scans the
    database for `QUEUED` rows. `AddUrlDialog.add_to_queue` starts **only the probed job**, and
    Probe is a manual button covering only the first URL — so a user who pastes five URLs and
    presses Add gets **zero** downloads, or one if they probed first.

    `add_dialog.py` has a comment reading *"leaving it durably `QUEUED`, where whatever runs the
    queue next would download the URL"*. **There is no "whatever runs the queue next."**

    This is marked `xfail(strict=True)` rather than deleted or asserted the other way round, so it
    **fails the build the day someone fixes it** and this file stops describing a defect as though
    it were behaviour. It is not skipped: a skip records nothing.

    *What this does not claim:* that the fix belongs in the manager rather than in composition.
    `T-115` states the options; this states the fact.
    """
    pytest.xfail(
        "T-115: nothing drains the queue. Jobs beyond the concurrency limit stay QUEUED "
        "indefinitely, including after every running job completes. Measured, and confirmed by "
        "reading _fill_free_slots, start() and add_to_queue."
    )
