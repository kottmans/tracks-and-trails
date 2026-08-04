"""One real download, against a real site (`T-037`, `-m network`).

Everything else in this project fakes the site. `tests/integration/test_end_to_end.py` runs real
yt-dlp against a local `http.server`, which proves that bytes move through the assembled
application — and proves nothing about whether a real extractor, on a real host, over TLS, still
produces what this code expects.

That gap is small and it is not zero, so it gets exactly one test: the offline fake is checked
against reality once, deliberately, on request.

**Excluded from every default run** (`ai/TESTING.md` §2). It reaches the network, so it fails for
reasons that are not this project's — a site reorganises, a CDN rate-limits, a runner has no
egress — and `§1` is explicit that a test failing because a site changed teaches nothing about
our code. Run it before a release, and when diagnosing extractor trouble.

**Never executed in the environment that wrote it.** The development machine ran it zero times;
the first real run is whoever runs `pytest -m network`. That is recorded rather than glossed,
because "written and never run" and "passing" are different claims and only one of them is true
here (`AGENTS.md` §7 — do not fabricate test results).
"""

import time
from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from tracks_and_trails import app as application
from tracks_and_trails.core.job_state import JobStatus

#: A small, stable, openly licensed file on a host that exists to serve archives.
#:
#: Chosen for durability rather than convenience: the Internet Archive keeps identifiers stable,
#: and the file is a few megabytes rather than a few hundred. The project already pins recorded
#: `info_dict` fixtures from the same host (`tests/fixtures/`), so a change there shows up in two
#: places at once, which is the useful behaviour.
#:
#: **Big Buck Bunny is CC BY 3.0, not public domain** (`T037-R2`) — the Blender Foundation's own
#: release poster carries the attribution. This comment said "public domain", which is the sort of
#: claim that is easy to repeat and wrong to rely on: `LIC-001` makes licence compatibility a
#: standing concern, and nothing here should teach a future reader a licence it does not have.
#: Downloading it in a test is fine under CC BY; redistributing it would need the attribution.
REAL_URL = "https://archive.org/download/BigBuckBunny_124/Content/big_buck_bunny_720p_surround.mp4"

#: The preset whose selector suits a direct media file — the same reasoning as the offline test:
#: a bare `video/mp4` declares no height, so the height-filtered default legitimately matches
#: nothing.
PRESET = "Best video available"


@pytest.mark.network
def test_one_real_url_downloads_end_to_end(
    qapp: QApplication,
    tmp_path: Path,
    spin: Callable[..., bool],
    record_property: Callable[[str, object], None],
) -> None:
    """The offline fake, checked against reality once.

    Deliberately the *same shape* as `test_a_url_becomes_a_file_with_the_bytes_it_reported`: if
    this passes and that one fails, the fake has drifted from the thing it stands in for, which
    is the only question this test is here to answer.
    """
    composition = application.compose(
        qapp,
        database=tmp_path / "queue.db",
        output_directory=tmp_path / "downloads",
        geometry_file=tmp_path / "window.toml",
    )
    try:
        dialog = composition.window.open_add_dialog()
        dialog._urls.setPlainText(REAL_URL)
        names = [dialog._preset_choice.itemText(i) for i in range(dialog._preset_choice.count())]
        dialog._preset_choice.setCurrentIndex(names.index(PRESET))
        # **Read before queued** (`UX-003`, `T-118`), and here that read is a real network probe
        # against a real site — which is exactly what this test exists to exercise.
        dialog.resolve()
        assert spin(
            lambda: bool(dialog.rows) and all(row.committable for row in dialog.rows), timeout=120
        ), dialog.status_text()
        dialog.add_to_queue()
        assert spin(lambda: bool(dialog.queued_job_ids), timeout=60), dialog.status_text()
        job_id = dialog.queued_job_ids[0]
        dialog.close()

        started = time.monotonic()
        composition.manager.start(job_id)
        # The queue **row**, since `UX-005` removed the detail pane. Still the UI rather than the
        # store, for the reason the pane was watched before it: the database leads the UI, so a
        # store-based wait passes in the gap before anything on screen has changed.
        queue = composition.window.queue_view
        assert queue is not None
        assert spin(
            lambda: (
                (job := queue.model.job_for(job_id)) is not None
                and job.status is JobStatus.COMPLETED
            ),
            timeout=600,
        ), (
            "the real download never completed. Before treating this as a defect, check whether "
            f"{REAL_URL} still resolves — this test fails for reasons that are not ours, which "
            "is why it is opt-in (ai/TESTING.md §1)"
        )
        record_property("real_download_seconds", round(time.monotonic() - started, 1))

        job = composition.store.get(job_id)
        assert job is not None and job.output_path is not None
        output = Path(job.output_path)
        assert output.exists()
        assert output.stat().st_size > 0, "a completed download produced an empty file"
        record_property("real_download_bytes", output.stat().st_size)
        assert job.bytes_total is None or output.stat().st_size == job.bytes_total, (
            f"the file is {output.stat().st_size} bytes and the queue recorded {job.bytes_total}"
        )
    finally:
        composition.shutdown.begin()
        assert spin(lambda: composition.shutdown.finished, timeout=120)
