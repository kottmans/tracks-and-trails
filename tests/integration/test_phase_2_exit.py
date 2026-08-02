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

import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
import tomllib
from collections.abc import Callable, Iterator
from contextlib import suppress
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

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
from tracks_and_trails.persistence.repositories import INTERRUPTED_ON_STARTUP


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

#: The limit the pool test configures. **Deliberately not `CONCURRENT` and not the default.**
#:
#: `core/settings.py`'s default is 3. The embedded launcher used to write its own `settings.toml`
#: with escaped newlines that produced a literal `\n` — invalid TOML — so `compose()` fell back to
#: defaults and this test measured a limit it had never set. It passed because the default happened
#: to equal the number it thought it had configured. A value the default cannot produce is what
#: makes the assertion mean something.
POOL_LIMIT = 2

#: Queued but deliberately **beyond** the limit, so some jobs have never started when the
#: application is killed or shut down. Criterion 5 is about workers that were never launched as
#: much as about ones that were.
QUEUED_BEYOND_LIMIT = 2


#: **Add URLs and then do nothing.** Every phase test drives the application this way, because
#: adding is everything a user does — anything that runs afterwards is the application admitting
#: its own queue.
#:
#: There were two of these until `T115-R2`. The other one primed the pool with `manager.start()`
#: in a loop that swallowed the refusal past the limit, because before `T-115` nothing else
#: drained the queue. Once Add had its own admission the loop started jobs the application had
#: already started, and the two launchers were the same program under two names — which hides
#: which route the evidence came from.
ADD_AND_WAIT = """
import os
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication

from tracks_and_trails import app as application

database, downloads, geometry, settings, paused, *urls = sys.argv[1:]
qapp = QApplication([])
composition = application.compose(
    qapp,
    database=Path(database),
    output_directory=Path(downloads),
    geometry_file=Path(geometry),
    settings_file=Path(settings),
)
# Pause is a runtime state, not a setting — `app.py` deliberately does not restore it — so a
# test that wants a paused queue has to ask for one here (`UX-001`).
if paused == "1":
    composition.manager.pause()
dialog = composition.window.open_add_dialog()
dialog._urls.setPlainText(chr(10).join(urls))
names = [dialog._preset_choice.itemText(i) for i in range(dialog._preset_choice.count())]
dialog._preset_choice.setCurrentIndex(names.index("Best video available"))
dialog.add_to_queue()
while len(dialog.queued_job_ids) < len(urls):
    qapp.processEvents()
job_ids = list(dialog.queued_job_ids)
dialog.close()
# **Nothing else happens here, and that is the whole point.** No `manager.start()`, no priming
# loop. Adding URLs is everything a user does, so anything that runs afterwards is the
# application admitting its own queue — the route `T-115` added and this file exists to prove.
#
# The application's own pid, not the launcher's: under a Windows venv `Popen` returns the launcher
# and a count beneath it cannot tell a worker-less tree from a healthy one (`T072-R1`).
print(os.getpid(), " ".join(job_ids), flush=True)
sys.exit(qapp.exec())
"""


RESTART_AND_REPORT = """
import json
import sys
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox

from tracks_and_trails import app as application
from tracks_and_trails.persistence import db
from tracks_and_trails.persistence.repositories import JobRepository

database, downloads, geometry, settings = sys.argv[1:5]
qapp = QApplication([])
composition = application.compose(
    qapp,
    database=Path(database),
    output_directory=Path(downloads),
    geometry_file=Path(geometry),
    settings_file=Path(settings),
)
# Read after compose() returns: recovery runs inside it, before anything can read the queue.
rows = {job.id: job.status.value for job in JobRepository(db.connect(database)).all_jobs()}
offered = composition.window.findChild(QMessageBox, "interruptedJobsDialog") is not None
print(json.dumps({"rows": rows, "offered": offered}), flush=True)
# **Shut down through the real lifecycle before exiting.** Calling sys.exit() with the writer
# thread still running aborts the interpreter with "QThread: Destroyed while thread
# 'queue-writer' is still running", which is a SIGABRT the parent reads as a failed start.
composition.shutdown.begin()
deadline = time.monotonic() + 60
while not composition.shutdown.finished and time.monotonic() < deadline:
    qapp.processEvents()
    time.sleep(0.01)
sys.exit(0 if composition.shutdown.finished else 2)
"""


def test_the_restart_helper_is_valid_python() -> None:
    """The recovery gate cannot reach `compose()` if its child script does not compile.

    Extended to **every** embedded launcher, not just the one that broke. All three are `\"\"\"`
    literals whose contents are compiled in another interpreter, so an escape that renders a string
    across two lines is a `SyntaxError` the parent only sees as a non-zero exit — and `T-115`'s gate
    would then report the defect it exists to report for entirely the wrong reason.
    """
    for name, script in (
        ("<phase-2-restart>", RESTART_AND_REPORT),
        ("<phase-2-add>", ADD_AND_WAIT),
    ):
        compile(script, name, "exec")


def restart_against(database: Path, tmp_path: Path) -> dict[str, Any]:
    """Start a **real composed application** against `database` and report what it found.

    `T088-R3`: this test used to call `JobRepository(...).recover_interrupted()` itself while its
    name, its comment and the evidence table all said "the next start". That is the seam the
    criterion is about — `compose()` recovers before anything can read the queue — and a test that
    performs the recovery cannot observe whether the application performs it.
    """
    environment = dict(os.environ, PYTHONPATH=str(REPO_ROOT / "src"), QT_QPA_PLATFORM="offscreen")
    restarted = subprocess.run(
        [
            sys.executable,
            "-c",
            RESTART_AND_REPORT,
            str(database),
            str(tmp_path / "downloads-restart"),
            str(tmp_path / "window-restart.toml"),
            str(write_settings(tmp_path / "settings-restart.toml", 1)),
        ],
        capture_output=True,
        text=True,
        env=environment,
        timeout=180,
    )
    assert restarted.returncode == 0, (
        f"the application did not start against the killed database: {restarted.stderr[-1500:]}"
    )
    return dict(json.loads(restarted.stdout.strip().splitlines()[-1]))


def write_settings(path: Path, concurrency: int) -> Path:
    """Write `settings.toml` **from the parent**, and assert it parses.

    The child used to write this itself, from a string embedded in a `\"\"\"` literal — and the
    escaping was wrong, so it produced a literal backslash-n and invalid TOML. `compose()` reports a
    settings problem and carries on with defaults (`ARC-008`), which is the right behaviour and
    which made the mistake invisible: the run looked normal and the configured limit never applied.

    Parsing it here is the guard. A test that silently gets defaults is not testing settings.
    """
    path.write_text(f"[queue]\nconcurrency = {concurrency}\n", encoding="utf-8")
    with path.open("rb") as handle:
        parsed = tomllib.load(handle)
    assert parsed["queue"]["concurrency"] == concurrency, f"unusable settings written: {parsed}"
    return path


def launch(
    script: str,
    *,
    database: Path,
    downloads: Path,
    geometry: Path,
    concurrency: int,
    urls: list[str],
    paused: bool = False,
) -> tuple[subprocess.Popen[str], int, list[str]]:
    """Start a real application in another interpreter and read its startup handshake."""
    downloads.mkdir(exist_ok=True)
    settings = write_settings(geometry.with_name("settings.toml"), concurrency)
    environment = dict(os.environ, PYTHONPATH=str(REPO_ROOT / "src"), QT_QPA_PLATFORM="offscreen")
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            script,
            str(database),
            str(downloads),
            str(geometry),
            str(settings),
            "1" if paused else "0",
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


def statuses(database: Path, job_ids: list[str], *, attempts: int = 3) -> dict[str, JobStatus]:
    """Each job's status, read through a **genuinely read-only** connection.

    **Not `db.connect`** — that runs `migrate()`, which *writes*. This helper is an out-of-process
    observer polling a database the application under test is actively writing, and opening a
    migrating connection against it every 100 ms is a write-write conflict wearing a reader's name.
    On Linux SQLite tolerated it; on `windows-latest` it produced `sqlite3.OperationalError: disk
    I/O error` and failed the run. `mode=ro` cannot migrate and cannot create.

    Querying the table directly rather than through `JobRepository` for the same reason: the
    repository is the application's, and this is not the application.

    **Transient errors are retried and then reported as no sample.** That is safe only because no
    caller feeds this straight into an `all(...)`: `all([])` is `True`, so a single missed read
    would have turned `T-115`'s strict xfail into an `XPASS` and **announced a repair that had not
    happened** (`T088-R4`). Use `settled()` and `snapshot()` below, which require every id to be
    present before they answer.
    """
    wanted = set(job_ids)
    for attempt in range(attempts):
        try:
            connection = sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)
            try:
                rows = connection.execute("SELECT id, status FROM jobs").fetchall()
            finally:
                connection.close()
        except sqlite3.Error:
            if attempt + 1 == attempts:
                return {}
            time.sleep(0.15)
            continue
        return {job_id: JobStatus(status) for job_id, status in rows if job_id in wanted}
    return {}


#: The states a job stops moving in.
TERMINAL = frozenset({JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED})


def snapshot(database: Path, job_ids: list[str], *, timeout: float = 30.0) -> dict[str, JobStatus]:
    """Every job's status, or **raise**. For authoritative reads (`T088-R4`).

    `statuses()` answers `{}` when it cannot read, which is right for a poll and wrong for a
    verdict — an assertion over an empty mapping is vacuously true. This retries to a deadline and
    fails loudly rather than reporting a queue that is empty because the disk was busy.
    """
    deadline = time.monotonic() + timeout
    found: dict[str, JobStatus] = {}
    while time.monotonic() < deadline:
        found = statuses(database, job_ids)
        if set(found) == set(job_ids):
            return found
        time.sleep(0.2)
    raise AssertionError(
        f"could not read all {len(job_ids)} jobs from {database} within {timeout}s; got "
        f"{sorted(found)}. This is a read failure, not an empty queue — see T088-R4"
    )


def settled(database: Path, job_ids: list[str]) -> bool:
    """Whether **every** job is in a terminal state. Never true on a partial read (`T088-R4`).

    The completeness check is the whole point: `all(...)` over a mapping missing rows — or over an
    empty one — is `True`, and the loops that use this are what decide whether `T-115` still
    reproduces.
    """
    if not job_ids:
        # "Every job in an empty list is terminal" is vacuously true and is the same trap one
        # level down. No caller passes an empty list, and if one ever does it is a defect rather
        # than a settled queue.
        return False
    found = statuses(database, job_ids)
    if set(found) != set(job_ids):
        return False
    return all(status in TERMINAL for status in found.values())


def wait_until(predicate: Callable[[], bool], timeout: float = 120.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return False


def running_count(database: Path, job_ids: list[str]) -> int:
    live = {JobStatus.PROBING, JobStatus.READY, JobStatus.RUNNING, JobStatus.POST_PROCESSING}
    return sum(1 for status in statuses(database, job_ids).values() if status in live)


def reap_application(process: subprocess.Popen[str], application_pid: int) -> None:
    """Take down the application **and everything under it** (`T088-R4`).

    `process.kill()` alone is not enough and this file used it in four places. Under a Windows
    virtualenv `Popen` returns the **launcher**, not the application — `T-066` found that, and
    `T072-R1` is why the handshake reports the application's own pid. Killing only what `Popen`
    holds can therefore leave a composed application, its writer thread and its workers running
    after the test that started them has passed.

    The captured tree is built while it is still intact: once the parent is gone its children are
    reparented and a walk finds nothing. `capture_the_doomed_tree` and `kill_the_application` are
    `test_end_to_end`'s, so there is one implementation of this reasoning rather than two.

    **The caller must have spawned with `isolate_the_application()`.** `kill_the_application` reaps
    the process *group* on POSIX; without isolation that group is pytest's own. `launch()` does it
    for every caller in this file.

    **`application_pid` is required.** An optional one with a `process.kill()` fallback would
    quietly reinstate the launcher-only teardown this helper exists to remove — the caller that
    forgot to thread the pid would get the old behaviour and no warning. Every `launch()` returns
    it.

    Only `NoSuchProcess` is tolerated, and only while walking: the application having already
    exited is ordinary. `AccessDenied` is not, and neither is a `wait` that times out —
    `kill_the_application` asserts no survivor, and this lets `wait` raise.
    """
    try:
        doomed = capture_the_doomed_tree(process, application_pid)
    except psutil.NoSuchProcess:
        # The application is already gone; only our own direct child can remain.
        doomed = []

    if doomed:
        kill_the_application(process, doomed)
    else:
        with suppress(ProcessLookupError):
            process.kill()
    process.wait(timeout=30)


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


# --- the helpers these criteria rest on (`T088-R4`) ----------------------------------------------


def test_settled_is_false_on_a_partial_read(tmp_path: Path) -> None:
    """**`all([])` is `True`**, and that is why this check exists.

    `statuses()` answers `{}` when it cannot read — on `windows-latest` a polling reader against a
    database the application is writing produced `disk I/O error`. Fed straight into an `all(...)`,
    one missed sample would have reported every job terminal, turned `T-115`'s strict xfail into an
    `XPASS`, and **announced a repair that never happened**.
    """
    database = tmp_path / "absent.db"

    assert statuses(database, ["job-1"]) == {}, "a database that cannot be read reported rows"
    assert not settled(database, ["job-1"]), "an unreadable database looked like a settled queue"
    assert not settled(database, []), "no ids at all cannot mean every id is terminal"


def test_snapshot_refuses_a_partial_read(tmp_path: Path) -> None:
    """An authoritative read fails loudly rather than reporting an empty queue (`T088-R4`)."""
    database = tmp_path / "absent.db"

    with pytest.raises(AssertionError, match="read failure, not an empty queue"):
        snapshot(database, ["job-1"], timeout=0.5)


def test_reap_application_kills_the_whole_tree(tmp_path: Path) -> None:
    """**`Popen.pid` is not always the application** (`T088-R4`, `T-066`, `T072-R1`).

    Under a Windows virtualenv `sys.executable` is a launcher and the application is its child, so
    a teardown that kills only what `Popen` returned leaves a composed application, its writer
    thread and its workers running after the test that started them has passed.

    Asserted with a plain parent-and-child pair rather than a real application: what is under test
    is that the *tree* is reaped, and a real composition would make the check depend on its
    shutdown behaviour instead.
    """
    source = (
        "import subprocess, sys, os, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
        "print(os.getpid(), child.pid, flush=True)\n"
        "time.sleep(120)\n"
    )
    # **`isolate_the_application()` is not optional.** `kill_the_application` reaps the process
    # *group* on POSIX, so a child sharing pytest's group takes pytest down with it — measured:
    # without this the test SIGKILLed its own runner, exit 137, with no report at all.
    process = subprocess.Popen(
        [sys.executable, "-c", source],
        stdout=subprocess.PIPE,
        text=True,
        **isolate_the_application(),
    )
    assert process.stdout is not None
    parent_pid, child_pid = (int(part) for part in process.stdout.readline().split())
    child = psutil.Process(child_pid)

    reap_application(process, parent_pid)

    _, alive = psutil.wait_procs([child], timeout=30)
    assert not alive, f"the grandchild (pid {child_pid}) outlived the reap"


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

    **The offer is covered here too**, since the correction for `T088-R3` made this a real restart:
    these are the only recovered rows in the suite that came from an actual kill rather than from a
    seeded database, so this is the one place the offer is observed over them. `T-082` covers the
    seeded case at composition level.

    *Does not cover:* resumption of partial bytes, which this phase does not do.
    """
    database = tmp_path / "queue.db"
    urls = [
        media_url(total_bytes=CLIP_BYTES, chunk_delay=0.5)
        for _ in range(CONCURRENT + QUEUED_BEYOND_LIMIT)
    ]
    process, application_pid, job_ids = launch(
        ADD_AND_WAIT,
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
        before = snapshot(database, job_ids)
        doomed = capture_the_doomed_tree(process, application_pid)

        kill_the_application(process, doomed)
        _, alive = psutil.wait_procs(workers, timeout=30)
        assert not alive, f"{len(alive)} worker(s) outlived the kill: {[p.pid for p in alive]}"
    finally:
        reap_application(process, application_pid)

    # **A real next start**, in its own interpreter (`T088-R3`). Recovery happens inside
    # `compose()`, so a test that called `recover_interrupted()` itself would be asserting on its
    # own call rather than on the application's.
    report = restart_against(database, tmp_path)
    after = {job_id: JobStatus(value) for job_id, value in report["rows"].items()}

    # **The same set the recovery uses**, not just `RUNNING`. A worker resolving a URL is as
    # interrupted as one writing bytes, and asserting only on `RUNNING` would make this test's
    # verdict depend on where in a session the kill happened to land.
    in_flight = [job_id for job_id, status in before.items() if status in INTERRUPTED_ON_STARTUP]
    assert in_flight, f"nothing was in flight at kill time: {before}"
    for job_id in in_flight:
        assert after[job_id] is JobStatus.FAILED, (
            f"{job_id} was in flight at the kill and the next start left it {after[job_id]}"
        )

    never_started = [job_id for job_id, status in before.items() if status is JobStatus.QUEUED]
    assert never_started, (
        f"every job had started, so this says nothing about the ones that had not: {before}"
    )
    for job_id in never_started:
        # **Not `is QUEUED`** — that assertion was correct until `T-115` and is now a race. The
        # next start *admits* durable queued intent, so by the time this reads the row the job may
        # legitimately be probing or running. What recovery must never do is treat a job that had
        # not started as interrupted, and that is what this says.
        assert after[job_id] is not JobStatus.FAILED, (
            f"{job_id} had never started and the next start recovered it as interrupted "
            f"({after[job_id]}) — recovery must only touch rows that were in flight"
        )

    # And the user is told, which is `T-082`'s half of the same criterion — asserted here because
    # this is the only place the rows come from a real kill rather than from a seeded database.
    assert report["offered"], (
        "the next start recovered the interrupted jobs and offered nothing, so a user who lost "
        "downloads to a crash sees failed rows and no acknowledgement"
    )


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
    process, application_pid, _job_ids = launch(
        ADD_AND_WAIT,
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
        reap_application(process, application_pid)


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

    **The limit is `POOL_LIMIT`, not `CONCURRENT`, and that is load-bearing.** `settings.py`'s
    default is 3; while the launcher wrote invalid TOML this test measured the default and passed
    because the default matched the number it believed it had set. A limit the default cannot
    produce is what turns this from a tautology into a test of `REQ-013`.

    *Does not cover:* raising the limit while running, which `T-078` covers; and the exact moment
    a slot is released, which is the manager's own tests.
    """
    database = tmp_path / "queue.db"
    urls = [
        media_url(total_bytes=CLIP_BYTES, chunk_delay=0.3)
        for _ in range(CONCURRENT + QUEUED_BEYOND_LIMIT)
    ]
    process, application_pid, job_ids = launch(
        ADD_AND_WAIT,
        database=database,
        downloads=tmp_path / "downloads",
        geometry=tmp_path / "window.toml",
        concurrency=POOL_LIMIT,
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
            if settled(database, job_ids):
                break
            time.sleep(0.1)
    finally:
        reap_application(process, application_pid)

    assert peak_rows, "no job was ever observed in flight, so no limit was ever tested"
    assert peak_rows <= POOL_LIMIT, (
        f"{peak_rows} jobs were in flight at once against a configured limit of {POOL_LIMIT}"
    )
    assert peak_workers <= POOL_LIMIT, (
        f"{peak_workers} worker processes existed at once against a configured limit of "
        f"{POOL_LIMIT}; the queue's own accounting agreed with the limit, so this is the pool and "
        "not the rows"
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

    *Does not cover:* attaching — `ARC-006` allows attach *or* refuse and this application refuses,
    so a future attach channel needs its own test rather than this one relaxed. **Nor the message
    the user sees:** this drives `compose()`, where the error is raised; the dialog and exit code 3
    live in `run()`, and `T-087`'s own tests cover that. What is asserted here is that the *lock*
    refuses under a full pool, which is the phase-level question.
    """
    database = tmp_path / "queue.db"
    urls = [media_url(total_bytes=CLIP_BYTES, chunk_delay=0.5) for _ in range(CONCURRENT)]
    process, application_pid, job_ids = launch(
        ADD_AND_WAIT,
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
                ADD_AND_WAIT,
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
        output = second.stderr + second.stdout
        assert "AlreadyRunningError" in output, (
            f"the second launch failed for some other reason than the lock: {second.stderr[-800:]}"
        )
        assert str(database) in output, "the refusal does not name the database it refused"
    finally:
        reap_application(process, application_pid)


# --- criterion 1: three at once, and the UI still answering ------------------------------------


def test_three_real_workers_each_write_their_whole_file(
    qapp: QApplication, tmp_path: Path, media_url: Callable[..., str]
) -> None:
    """**Exit criterion 1's process half, and deliberately only that half** (`T088-R2`).

    This test used to be named for progress and interactivity and claimed both. It observes
    neither: it samples durable status dictionaries and terminal file sizes, and never sees a
    progress byte, a signal, a table cell or an event-loop tick. **A mutation dropping every live
    progress update passes it.** `T088-R2` filed that as an overclaim and was right.

    What it does prove, which nothing else does: three **real spawned worker processes** run at
    once against a real extractor and each writes its own complete file — three distinct outputs of
    the full size, not one file three times and not a shared counter.

    The claims this no longer makes are covered, and the evidence table cites them rather than this:

    - *independent accurate progress* — `tests/ui/test_queue_view.py::
      test_three_concurrent_downloads_show_independent_progress` and
      `tests/integration/test_composition.py::test_three_concurrent_downloads_each_keep_their_own_row`
    - *UI interactive throughout* — `tests/integration/test_composition.py::
      test_the_interface_stays_inside_its_budget_while_three_downloads_run`
    """
    database = tmp_path / "queue.db"
    downloads = tmp_path / "downloads"
    urls = [media_url(total_bytes=CLIP_BYTES, chunk_delay=0.3) for _ in range(CONCURRENT)]
    process, application_pid, job_ids = launch(
        ADD_AND_WAIT,
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
            sample = statuses(database, job_ids)
            if sample and (not transitions or sample != transitions[-1]):
                transitions.append(sample)
            if settled(database, job_ids):
                break
            time.sleep(0.1)
        # **Taken before teardown** (`T088-R4`): the database is the application's, and reading it
        # after the process tree is reaped is a race with whatever the OS is still closing.
        final = snapshot(database, job_ids)
    finally:
        reap_application(process, application_pid)

    assert len(final) == CONCURRENT
    assert all(status is JobStatus.COMPLETED for status in final.values()), (
        f"not every concurrent download completed: {final}"
    )
    assert len(transitions) > 1, (
        "the application never advanced its own state while three workers ran. **This is a "
        "liveness check, not a responsiveness one** — see the docstring; the interactivity claim "
        "belongs to the composed budget test"
    )

    files = [path for path in downloads.glob("*") if path.is_file()]
    written = sorted(path.stat().st_size for path in files)
    assert len(written) == CONCURRENT, (
        f"expected {CONCURRENT} files, found {[f.name for f in files]}"
    )
    assert all(size == CLIP_BYTES for size in written), (
        f"three concurrent downloads did not each write the whole clip: {written}"
    )
    assert len({path.name for path in files}) == CONCURRENT, (
        "three downloads produced fewer than three distinct filenames, so they were not three "
        "independent outputs"
    )


# --- what proving the phase found: the queue does not drain -----------------------------------


def test_every_queued_job_eventually_starts_as_slots_free(
    qapp: QApplication, tmp_path: Path, media_url: Callable[..., str]
) -> None:
    """**`T-115`, asserted as the behaviour that is wanted rather than the one that happens.**

    The previous version of this test called `pytest.xfail()` unconditionally with no setup and no
    assertion. `T088-R1` filed that as High and was right: it reports `XFAIL` whatever the code
    does, so the gate this file promised — *fixing it fails the build until the test is inverted* —
    could never fire. A strict marker over a real reproduction is what makes that promise real:
    when `T-115` is fixed this becomes `XPASS` and the build goes red until someone removes the
    marker.

    **The assertion deliberately does not choose a layer.** It says every queued job eventually
    runs with no user action beyond Add — not that the manager, or composition, or a startup sweep
    is what admits it. Which of those owns durable admission is the maintainer's design call, and
    the review's own recommendation is a direction rather than an approval.

    **Driven through the user route alone** (`T088-R1`). The other phase tests use a launcher that
    calls `manager.start()` per job after Add, to prime a pool they then observe. This one must
    not: with that priming, a change making `start()` park instead of raise would admit every job
    and pass this while the application still admitted nothing by itself. `Add` is all a user
    does, so `Add` is all this does.

    **This was `xfail(strict=True)` and is now an ordinary test** — `T-115` is fixed and the marker
    was removed the moment it reported `XPASS(strict)`, which is the gate working: the promise was
    that closing `T-115` reddens the build until someone inverts this, and it did.

    Before the fix, on this route, **nothing ran at all** — the dialog started only a probed job and
    there is no probe here. Five URLs, a limit of three, and zero downloads.
    """
    database = tmp_path / "queue.db"
    urls = [
        media_url(total_bytes=CLIP_BYTES, chunk_delay=0.05)
        for _ in range(CONCURRENT + QUEUED_BEYOND_LIMIT)
    ]
    process, application_pid, job_ids = launch(
        ADD_AND_WAIT,
        database=database,
        downloads=tmp_path / "downloads",
        geometry=tmp_path / "window.toml",
        concurrency=CONCURRENT,
        urls=urls,
    )
    try:
        # Generous, because the claim is "eventually" and a slow agent must not be the reason this
        # reports the defect. Three downloads of this size finish in a few seconds.
        # **Completeness before `all`** (`T088-R4`). `all([])` is `True`, so one missed read would
        # turn this strict xfail into an `XPASS` and announce a repair that never happened.
        def every_job_completed() -> bool:
            found = statuses(database, job_ids)
            return set(found) == set(job_ids) and all(
                status is JobStatus.COMPLETED for status in found.values()
            )

        drained = wait_until(every_job_completed, timeout=90)
        final = snapshot(database, job_ids)
    finally:
        reap_application(process, application_pid)

    assert drained, (
        f"{sum(1 for s in final.values() if s is JobStatus.QUEUED)} of {len(job_ids)} jobs were "
        f"still QUEUED after Add with nothing else done — nothing admits durable queued intent. "
        f"Final: "
        f"{ {k[:6]: v.value for k, v in final.items()} }"
    )


def test_a_queue_left_by_a_previous_run_starts_on_the_next_launch(
    qapp: QApplication, tmp_path: Path, media_url: Callable[..., str]
) -> None:
    """**`T-115`'s restart half**, which the Add route alone cannot reach.

    A user who closes the application with work still queued must not find it inert next time. The
    in-memory waiting list dies with the process, so durable `QUEUED` intent has to be admitted at
    startup — and that is the half a dialog-only fix would have missed.

    **Nothing recovered is admitted**, which is the other half of the same seam.
    `recover_interrupted` moves in-flight rows to `FAILED` before this reads them, so a job that
    was *running* when the
    application died is offered for retry (`T-082`) rather than restarted unattended. That was
    `T081-R4`, and it is why the startup read happens after recovery rather than before.
    """
    database = tmp_path / "queue.db"
    # **A limit of one, and three URLs.** With the limit equal to the URL count every job is
    # admitted at once and nothing is left `QUEUED` to test — which is how the first version of
    # this test passed vacuously on its own setup rather than on the behaviour.
    urls = [media_url(total_bytes=CLIP_BYTES, chunk_delay=0.3) for _ in range(3)]

    # First launch: add, then kill while two are still waiting for the first to finish.
    process, application_pid, job_ids = launch(
        ADD_AND_WAIT,
        database=database,
        downloads=tmp_path / "downloads",
        geometry=tmp_path / "window.toml",
        concurrency=1,
        urls=urls,
    )
    reap_application(process, application_pid)
    left_behind = snapshot(database, job_ids)
    # The recovery on the *next* launch will move anything in flight to FAILED; what this test is
    # about is the rows that never started at all.
    assert any(status is JobStatus.QUEUED for status in left_behind.values()), (
        f"nothing was left queued, so this says nothing about the next launch: {left_behind}"
    )

    # Second launch: the same database, and nothing done but starting the application.
    process, application_pid, _second = launch(
        ADD_AND_WAIT,
        database=database,
        downloads=tmp_path / "downloads-second",
        geometry=tmp_path / "window-second.toml",
        concurrency=CONCURRENT,
        urls=[media_url(total_bytes=CLIP_BYTES, chunk_delay=0.05)],
    )
    try:
        left_queued = [
            job_id for job_id, status in left_behind.items() if status is JobStatus.QUEUED
        ]

        def the_old_queue_finished() -> bool:
            found = statuses(database, left_queued)
            return set(found) == set(left_queued) and all(
                status is JobStatus.COMPLETED for status in found.values()
            )

        drained = wait_until(the_old_queue_finished, timeout=120)
        final = snapshot(database, left_queued)
    finally:
        reap_application(process, application_pid)

    assert drained, (
        f"the previous run's queue was still inert after a restart: "
        f"{ {k[:6]: v.value for k, v in final.items()} }"
    )


def test_a_paused_queue_admits_and_still_starts_nothing(
    qapp: QApplication, tmp_path: Path, media_url: Callable[..., str]
) -> None:
    """`UX-001`: admission is a claim on the next free slot, **not a start**.

    The risk `T-115` introduces is precisely this — a fix that drains the queue could drain it past
    a pause, which is the one thing pause exists to stop. Asserted against a real application whose
    settings pause it before anything is added.
    """
    database = tmp_path / "queue.db"
    urls = [media_url(total_bytes=CLIP_BYTES, chunk_delay=0.3) for _ in range(CONCURRENT)]
    process, application_pid, job_ids = launch(
        ADD_AND_WAIT,
        database=database,
        downloads=tmp_path / "downloads",
        geometry=tmp_path / "window.toml",
        concurrency=CONCURRENT,
        urls=urls,
        paused=True,
    )
    try:
        # Long enough that an unpaused queue would have started and finished all three.
        time.sleep(6)
        while_paused = snapshot(database, job_ids)
    finally:
        reap_application(process, application_pid)

    assert all(status is JobStatus.QUEUED for status in while_paused.values()), (
        f"a paused queue started work: { {k[:6]: v.value for k, v in while_paused.items()} }"
    )
