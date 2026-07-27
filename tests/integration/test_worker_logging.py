"""`T-038`: a real worker's diagnostics reach the parent's log, redacted (`REQ-026`).

The unit tests prove the queue handler and the formatter separately. This proves the thing the
acceptance criterion actually names — that a **spawned** worker's line lands in the application's
log file with the credential gone — against a real process, a real queue and a real file
(`ai/TESTING.md` §6: the process boundary is not mocked).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication

from tests.integration.test_manager import FakeRepository, make_job
from tracks_and_trails.core import logging as app_logging
from tracks_and_trails.downloader.manager import DownloadManager
from tracks_and_trails.downloader.protocol import Succeeded, WorkerFinished

#: Shaped like a real signed-URL parameter, and unmistakable in a diff if it ever escapes.
TOKEN = "sk-live-7c6c-must-not-appear"  # noqa: S105 - a marker, not a secret


def a_worker_that_logs(kind: Any, job_id: str, request: Any, queue: Any, **kwargs: Any) -> None:
    """A real spawned child that logs a tokenised URL and then finishes its session.

    Deliberately **not** formatting anything itself: it calls `prepare_this_worker`, which is
    what production calls, and lets the record travel. That is the property under test — a worker
    cannot emit an unredacted line because it does not do the rendering.
    """
    from tracks_and_trails.downloader import worker

    worker.prepare_this_worker(kwargs.get("log_queue"))
    logging.getLogger("tracksandtrails.worker").warning(
        "probing https://example.invalid/v?token=%s", TOKEN
    )
    queue.put(Succeeded(job_id=job_id, output_path="/written/clip.mp4", total_bytes=1))
    queue.put(WorkerFinished(job_id=job_id, exit_code=0))


def test_a_spawned_workers_line_reaches_the_parents_log_without_its_token(
    tmp_path: Path, qapp: QCoreApplication
) -> None:
    repository = FakeRepository()
    repository.add(make_job("job-1", "https://example.invalid/clip", tmp_path))
    log_path = app_logging.configure_logging(directory=tmp_path, level=logging.DEBUG)
    download = DownloadManager(repository, entry_point=a_worker_that_logs)

    try:
        download.start("job-1")
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and not download.is_idle:
            qapp.processEvents()
            time.sleep(0.05)

        # The listener is a thread draining a queue; the record is in flight, not lost.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and "probing" not in log_path.read_text("utf-8"):
            qapp.processEvents()
            time.sleep(0.05)
        for handler in logging.getLogger("tracksandtrails").handlers:
            handler.flush()
        written = log_path.read_text("utf-8")
    finally:
        app_logging.stop_listening_for_worker_logs()
        tree = logging.getLogger("tracksandtrails")
        for handler in list(tree.handlers):
            tree.removeHandler(handler)
            handler.close()

    assert "probing" in written, (
        f"the worker's line never reached the parent's log. Written:\n{written}"
    )
    assert "example.invalid" in written, "the diagnostic lost the address it was about"
    assert TOKEN not in written, (
        "the worker's token reached the log file. Records travel unformatted so the parent's "
        "handlers redact them; if this fails, something formatted in the child."
    )
