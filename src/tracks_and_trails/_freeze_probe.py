"""Frozen-build self-test for the `ARC-002` process model (`T-020`).

**Why this ships in the application rather than living in `tests/`.** The failure it guards
against only exists in a frozen binary. There, `sys.executable` is the application itself, so
`multiprocessing` starting a child re-executes the *app* — and without
`multiprocessing.freeze_support()` running before anything else, that child runs the whole
program again instead of the worker function. The result is a recursive launch, not a subtle
misbehavior. Testing it therefore requires code inside the frozen artifact, spawning a real
child through the real entry point (`REL-001`, `ARCHITECTURE.md` §3 and §12).

**This module belongs to none of `ARCHITECTURE.md` §4's four layers.** It is listed in §4's
structure and described in §12, but as frozen-build diagnostic infrastructure rather than as
product code — which is what the leading underscore marks. It imports no Qt so a spawned child
inherits none (`ARC-002`), and is reachable only via an explicit `--spawn-probe` argument.
`T-012` builds the real worker; this never becomes one.

**How "exactly one top-level application process" is asserted.** `record_app_start` is called
by `main()` in `__main__.py` — the first thing every top-level start reaches — and appends a
line to the file named by `TT_PROBE_LOG`. Exactly one line means the child ran the worker
function; more than one means it relaunched the application.

The marker deliberately lives in `main()` rather than in `run_probe`. An earlier version
recorded it inside the probe, which does not work: a relaunched child inherits multiprocessing's
own argument vector, not the parent's, so it never re-enters `--spawn-probe` and the count stays
at one while the recursion happens anyway. That was found by actually removing
`freeze_support()` and rebuilding, not by reasoning about it.
"""

import multiprocessing
import os
import sys
import time
from multiprocessing.queues import Queue as QueueType
from pathlib import Path
from typing import Any

from tracks_and_trails.downloader import process_tree

#: Names the file that records one line per top-level application start. Set by the caller
#: (CI, or a test); when unset the probe still runs but the recursion count is not recorded.
PROBE_LOG_ENV = "TT_PROBE_LOG"

#: The single message the child sends back. Not a real IPC protocol — `T-011` defines that.
PROBE_MESSAGE = "worker-alive"

#: A well-formed URL for the extractor the probe names. The 11-character id is not cosmetic:
#: yt-dlp's pattern requires it, and a shorter placeholder makes `suitable()` return False and
#: the gate fail for the wrong reason. Never fetched — only pattern-matched (`T033-R2`).
_KNOWN_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

#: A URL the same extractor must *not* claim. Without it, an extractor whose predicate always
#: returned True would satisfy the check above.
_UNRELATED_URL = "https://example.com/not-a-video"

#: Generous: a cold frozen child on a loaded CI runner starts far slower than a source one.
TIMEOUT_SECONDS = 120


#: The file the download probe fetches, and the reason it is that one.
#:
#: **Deliberately the same URL as `tests/network/test_real_download.py`.** If the probe and that
#: test ever disagree, the difference is the artifact rather than the site — which is the only
#: question worth asking of a clean machine. The Internet Archive keeps identifiers stable, and
#: `T037-R2` established the licence: Big Buck Bunny is **CC BY 3.0**, not public domain.
#: Downloading it is fine under that licence; redistributing it would need the attribution.
DOWNLOAD_PROBE_URL = (
    "https://archive.org/download/BigBuckBunny_124/Content/big_buck_bunny_720p_surround.mp4"
)


#: Names a file the probes append their report lines to, as well as printing them (`T-319`).
#:
#: **A windowed build has no `stdout`.** `REL-001`'s release artifact is built `console=False` so a
#: user gets no console window behind the application, and on Windows that means the four probes
#: CI depends on print into nothing. This is the same shape as `PROBE_LOG_ENV` above rather than a
#: fifth mechanism: one variable, set by the caller, ignored when unset.
PROBE_REPORT_ENV = "TT_PROBE_REPORT"


def say(line: str, *, error: bool = False) -> None:
    """Print a probe's report line, and append it to the report file when one is configured.

    Both, never either: the console build's output is what a person reads when running the probe
    by hand, and the file is what CI reads when the build has no console to read.
    """
    print(line, file=sys.stderr if error else sys.stdout)
    path = os.environ.get(PROBE_REPORT_ENV)
    if not path:
        return
    try:
        with Path(path).open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        # The report is evidence, not the probe's purpose. A probe that failed because it could
        # not write its own log would be reporting on the log.
        return


def record_app_start() -> None:
    """Record one top-level application start, if a probe log is configured.

    Called from `main()`. A no-op unless `TT_PROBE_LOG` is set, which it never is in normal
    use — this costs one environment lookup on the startup path and buys the only direct
    evidence that a frozen child did not relaunch the app.
    """
    path = os.environ.get(PROBE_LOG_ENV)
    if not path:
        return
    try:
        with Path(path).open("a", encoding="utf-8") as handle:
            handle.write(f"app-start pid={os.getpid()} frozen={is_frozen()} argv={sys.argv[1:]}\n")
    except OSError:
        return


def probe_child(queue: QueueType[Any]) -> None:
    """The spawned worker. Module-level so `spawn` can pickle it by reference.

    Sends one message and exits. Deliberately trivial: this task answers whether spawning
    from a frozen binary works at all, not whether any real work does.
    """
    queue.put({"message": PROBE_MESSAGE, "pid": os.getpid(), "frozen": is_frozen()})


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def run_probe() -> int:
    """Spawn one child, exchange one message, and exit. Returns a process exit code."""
    context = multiprocessing.get_context("spawn")
    queue: QueueType[Any] = context.Queue()
    child = context.Process(target=probe_child, args=(queue,), name="tt-freeze-probe")

    # `T258-R3`: the shipped `--spawn-probe` path spawns without a manager, and the pre-bootstrap
    # window is not specific to a target. This is a product-owned `Process.start()` and goes
    # through the same seam as the other two.
    process_tree.start_contained(child)
    try:
        payload = queue.get(timeout=TIMEOUT_SECONDS)
    # Any failure at all is a probe failure; there is no exception here worth re-raising.
    except Exception as exc:
        child.terminate()
        child.join(timeout=TIMEOUT_SECONDS)
        say(f"FAIL: no message from the spawned child: {exc!r}", error=True)
        return 1
    finally:
        child.join(timeout=TIMEOUT_SECONDS)

    say(f"frozen           {is_frozen()}")
    say(f"parent pid       {os.getpid()}")
    say(f"child pid        {payload.get('pid')}")
    say(f"child frozen     {payload.get('frozen')}")
    say(f"message          {payload.get('message')}")
    say(f"child exitcode   {child.exitcode}")

    if payload.get("message") != PROBE_MESSAGE:
        say(f"FAIL: unexpected message {payload!r}", error=True)
        return 1
    if payload.get("pid") == os.getpid():
        say("FAIL: the worker ran in the parent process; no child was spawned", error=True)
        return 1
    if child.is_alive():
        say("FAIL: the child is still alive after join; it would be orphaned", error=True)
        return 1
    if child.exitcode != 0:
        say(f"FAIL: child exited {child.exitcode}", error=True)
        return 1

    say("OK: spawned a child from this build, exchanged one message, and reaped it")
    return 0


def run_ytdlp_probe() -> int:
    """Assert the frozen artifact actually carries a usable yt-dlp (`T-033`, `OPS-002`).

    **Importing yt-dlp is not the test.** `import yt_dlp` succeeds against the core alone, which
    is precisely what makes the packaging failure look like site breakage: the app launches, and
    every URL fails to find an extractor. So this resolves an extractor *by name* through
    yt-dlp's lazy machinery, which is the part static analysis cannot see.

    Resolution goes through `downloader.worker`, the only module permitted to import yt-dlp
    (`ARCHITECTURE.md` §6). That is not a workaround — it means the probe exercises the real
    `OPS-002` resolution path inside the artifact rather than a parallel one.
    """
    from tracks_and_trails.downloader.environment import (
        BASELINE_YTDLP_VERSION,
        normalise_version,
        ytdlp_candidates,
    )
    from tracks_and_trails.downloader.worker import _import_ytdlp, bundled_solver

    try:
        resolved = _import_ytdlp(ytdlp_candidates(None))
    except ImportError as error:
        say(f"FAIL: no usable yt-dlp in the frozen artifact: {error}", error=True)
        return 1

    say(f"ytdlp version   {resolved.version}")
    say(f"ytdlp source    {resolved.source}")
    say(f"ytdlp pin       {BASELINE_YTDLP_VERSION}")

    # `T033-R1`: the first acceptance criterion. Printing the version is not asserting it — a
    # stale or wrong yt-dlp passed every other check here, because "some yt-dlp with lots of
    # extractors" is exactly what a wrongly-pinned build also produces. `OPS-002` promises a
    # *pinned, tested* baseline, and this is the only place that promise is verifiable inside
    # the artifact.
    #
    # Compared normalised: the pin reads `2026.7.4` and the package reports `2026.07.04`.
    if normalise_version(resolved.version) != normalise_version(BASELINE_YTDLP_VERSION):
        say(
            f"FAIL: the artifact bundles yt-dlp {resolved.version}, but this build pins "
            f"{BASELINE_YTDLP_VERSION}. The frozen baseline is not the tested one (T-033, "
            "OPS-002).",
            error=True,
        )
        return 1

    extractors = resolved.module.extractor.gen_extractor_classes()
    names = [cls.IE_NAME for cls in extractors]
    say(f"extractors      {len(names)}")

    # A handful of extractors is what you get when only the core was bundled. A real yt-dlp has
    # hundreds; the exact number changes upstream, so the bound is deliberately loose.
    if len(names) < 100:
        say(
            f"FAIL: only {len(names)} extractors resolved. The artifact carries yt-dlp's core "
            "without its extractors, so every URL would fail as if the site had changed "
            "(T-033).",
            error=True,
        )
        return 1

    # Resolution by name is the operation a download actually performs.
    #
    # `get_info_extractor` *raises* `KeyError` for an unknown name — it does not return None.
    # An earlier `matched is None` check here was therefore dead code, and the failure it was
    # written to explain escaped as a bare traceback instead. The job still went red, so the
    # gate worked; but under `OPS-003` a Windows failure is diagnosed from this log and nothing
    # else, and "KeyError: 'YoutubeIE'" does not say that the artifact shipped without its
    # extractors. Found by mutation-checking the probe rather than by a failure.
    try:
        placeholder = resolved.module.extractor.get_info_extractor("Youtube")
    except KeyError:
        say(
            "FAIL: yt-dlp is present and reports extractors, but a known extractor could not "
            "be resolved by name. The lazy-extractor machinery did not survive freezing "
            "(T-033).",
            error=True,
        )
        return 1

    # `T033-R2`: **resolving the name is not the gate.** `get_info_extractor` hands back a class
    # from `yt_dlp.extractor.lazy_extractors`, which is a generated stub table — it imports no
    # extractor code at all. With `yt_dlp.extractor.youtube` made unimportable, this probe still
    # reported 1751 extractors, "resolved youtube", and exit 0, while actually using the
    # extractor failed with `ModuleNotFoundError`. That is precisely the shipped-but-broken
    # artifact T-033 exists to catch, passing its own gate.
    #
    # Instantiating the placeholder is what triggers the real import: the lazy class swaps
    # itself for the concrete one on construction.
    try:
        extractor = placeholder()
    except ImportError as error:
        say(
            f"FAIL: the extractor's real module could not be imported: {error}. The artifact "
            "carries yt-dlp's lazy extractor table but not the extractor code behind it, so "
            "every matching URL would fail as if the site had changed (T-033).",
            error=True,
        )
        return 1

    real = type(extractor)
    say(f"resolved        {real.IE_NAME} from {real.__module__}")

    if "lazy" in real.__module__:
        say(
            f"FAIL: {real.IE_NAME} is still the lazy placeholder ({real.__module__}); the "
            "concrete extractor module was never loaded (T-033).",
            error=True,
        )
        return 1

    # The stable, offline half of what an extractor does: decide whether it handles a URL. No
    # network — a packaging gate that needs the internet is a gate that fails on a bad day.
    if not real.suitable(_KNOWN_URL) or real.suitable(_UNRELATED_URL):
        say(
            f"FAIL: {real.IE_NAME} loaded but does not match its own URL pattern; the "
            "extractor code in this artifact is not the one it claims to be (T-033).",
            error=True,
        )
        return 1

    # **Asked, not performed** (`T033-R5`). Where the solver lives, what it is called, which hash
    # vouches for it and how it is loaded are upstream's business and change when upstream changes
    # them — so they live behind `downloader/worker.py` with the rest of the yt-dlp coupling
    # (`ARCHITECTURE.md` §6). This module reads a `SolverReport` and decides an exit code, which
    # is all a probe should know.
    solver = bundled_solver(resolved.module)
    if not solver.usable:
        say(f"FAIL: {solver.problem} (T-033, T033-R4)", error=True)
        return 1
    say(f"solver          {solver.name} v{solver.version}, hash verified")
    say(f"solver extras   {len(solver.also)} also present: {', '.join(solver.also) or '-'}")

    say("OK: the frozen artifact carries a usable yt-dlp with its extractors")
    return 0


def run_database_probe() -> int:
    """Assert the frozen artifact can actually create its database (`T-014`, `T014-R3`).

    **Collecting the `.sql` files in the spec is not the test.** PyInstaller follows imports and
    nothing imports a `.sql`, so the migrations are collected only if named — and when they are
    not, the directory is simply *absent* rather than broken. `available_migrations()` then
    returns an empty list, a version-0 database with no tables is created, and the first write
    fails with `no such table: jobs`, which reads as a code bug rather than a build one.

    So this builds a real database in a temporary directory and writes a real job through the
    real repository, inside the artifact. Nothing here is a parallel implementation: it is the
    same `connect` a launch performs.
    """
    import tempfile

    from tracks_and_trails.core.models import DownloadRequest, Job
    from tracks_and_trails.persistence import db
    from tracks_and_trails.persistence.repositories import JobRepository

    try:
        migrations = db.available_migrations()
    except (OSError, ValueError) as error:
        say(f"FAIL: the migration directory is unusable: {error}", error=True)
        return 1

    say(f"migrations      {len(migrations)}")
    if not migrations:
        say(
            "FAIL: the frozen artifact carries no migration SQL. The spec did not collect "
            "persistence/migrations/*.sql, so the database would be created empty and every "
            "write would fail with 'no such table' (T-014, T014-R3).",
            error=True,
        )
        return 1

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "probe.sqlite3"
        try:
            with db.open_database(path) as connection:
                version = db.schema_version(connection)
                say(f"schema version  {version}")
                if version != db.latest_version():
                    say(
                        f"FAIL: the database came up at version {version}, expected "
                        f"{db.latest_version()}.",
                        error=True,
                    )
                    return 1

                repository = JobRepository(connection)
                request = DownloadRequest(
                    url="https://example.invalid/probe",
                    output_directory=directory,
                    format_selector="best",
                    output_template="%(title)s.%(ext)s",
                )
                job = Job(id="probe", url=request.url, request=request)
                repository.add(job)
                if repository.get("probe") != job:
                    say(
                        "FAIL: a job written inside the artifact did not read back.",
                        error=True,
                    )
                    return 1
        except Exception as error:
            say(f"FAIL: the frozen artifact could not use its database: {error}", error=True)
            return 1

    say("database        ok")
    return 0


#: The version the update probe installs. Not a plausible yt-dlp release: a probe that asserted a
#: real-looking number could be satisfied by the baseline leaking through.
_PROBE_YTDLP_VERSION = "9000.1.1"


def _probe_wheel(version: str) -> bytes:
    """A minimal but genuinely importable yt-dlp, as a wheel.

    **Minimal is the honest scope here, and the boundary is worth stating.** This probe proves the
    *update path* inside the frozen artifact — install lands where a frozen worker resolves, and
    revert restores the baseline — which is the sequence `docs/project/TESTING.md`'s release gate
    names. It does **not** prove a download runs on the installed copy: that is criterion 2, and
    `tests/integration/test_end_to_end.py` proves it against a real yt-dlp and a real transfer
    (`T198-R1`). A frozen probe cannot reach a site, and a package thin enough to ship inside one
    could not run a download anyway — so claiming it would be the vacuous half of `T198-R1` again.

    `__init__` imports `.version` because that is how the real package exposes
    `yt_dlp.version.__version__`; a copy without it imports and then fails on the attribute.
    """
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "yt_dlp/__init__.py", "from . import version\n__version__ = version.__version__\n"
        )
        archive.writestr("yt_dlp/version.py", f"__version__ = {version!r}\nCHANNEL = 'probe'\n")
        archive.writestr(f"yt_dlp-{version}.dist-info/METADATA", f"Version: {version}\n")
    return buffer.getvalue()


def run_ytdlp_update_probe() -> int:
    """Install, resolve in a spawned child, revert, resolve again — inside the artifact.

    **`T198-R2`.** The frozen jobs built the artifact, probed its bundled baseline and ran the
    generic spawn smoke; none of them ever invoked the updater, resolved an installed copy in a
    spawned child, or reverted. Two green frozen jobs therefore said nothing about criterion 4,
    and `docs/project/TESTING.md`'s release-gate item 10 names the missing sequence independently.

    Everything here is the production path: `install_latest` is what the button calls,
    `resolve_in_a_child` spawns `worker.spawn_resolution`, and `revert_to_baseline` is what the
    revert does. The only substitutions are the *index* — served from memory, because a CI runner
    must not depend on PyPI for a gate — and a temporary user directory, because a probe must not
    write into the real one.

    No Qt: `resolve_in_a_child` lives in `downloader/ytdlp_resolution.py` precisely so this module
    can use it and a spawned child still inherits none (`ARC-002`).
    """
    import contextlib
    import hashlib
    import io
    import json
    import tempfile

    from tracks_and_trails.downloader.environment import (
        BASELINE_YTDLP_VERSION,
        normalise_version,
    )
    from tracks_and_trails.downloader.ytdlp_resolution import resolve_in_a_child
    from tracks_and_trails.downloader.ytdlp_update import (
        PYPI_INDEX,
        install_latest,
        revert_to_baseline,
    )

    payload = _probe_wheel(_PROBE_YTDLP_VERSION)
    wheel_url = f"https://files.pythonhosted.org/yt_dlp-{_PROBE_YTDLP_VERSION}-py3-none-any.whl"
    document = {
        "info": {"version": _PROBE_YTDLP_VERSION},
        "urls": [
            {
                "packagetype": "bdist_wheel",
                "filename": f"yt_dlp-{_PROBE_YTDLP_VERSION}-py3-none-any.whl",
                "url": wheel_url,
                "digests": {"sha256": hashlib.sha256(payload).hexdigest()},
            }
        ],
    }
    responses = {PYPI_INDEX: json.dumps(document).encode(), wheel_url: payload}

    @contextlib.contextmanager
    def opener(requested: str) -> Any:
        yield io.BytesIO(responses[requested])

    with tempfile.TemporaryDirectory(prefix="tt-update-probe-") as workspace:
        directory = Path(workspace) / "ytdlp"

        before = resolve_in_a_child(directory)
        say(f"before install  {before.version} — {before.source}")
        if normalise_version(before.version) != normalise_version(BASELINE_YTDLP_VERSION):
            say(
                f"FAIL: the artifact resolves {before.version}, not the pinned baseline "
                f"{BASELINE_YTDLP_VERSION}",
                error=True,
            )
            return 1

        installed = install_latest(directory, opener)
        say(f"installed       {installed.version}")

        after = resolve_in_a_child(directory)
        say(f"after install   {after.version} — {after.source}")
        if after.version != _PROBE_YTDLP_VERSION or not after.is_user_managed:
            say(
                "FAIL: a spawned child did not resolve the installed copy — an update inside the "
                f"frozen artifact lands where nothing reads it (got {after.version!r} from "
                f"{after.source!r}; rejected={after.rejected})",
                error=True,
            )
            return 1

        if not revert_to_baseline(directory):
            say("FAIL: revert reported nothing to remove", error=True)
            return 1

        restored = resolve_in_a_child(directory)
        say(f"after revert    {restored.version} — {restored.source}")
        if normalise_version(restored.version) != normalise_version(BASELINE_YTDLP_VERSION):
            say(
                f"FAIL: reverting did not restore the baseline (got {restored.version})",
                error=True,
            )
            return 1
        if restored.is_user_managed:
            say("FAIL: the reverted copy is still being resolved", error=True)
            return 1

    say("OK: install, resolve in a child, and revert all work in the frozen artifact")
    return 0


def run_download_probe(url: str | None = None) -> int:
    """Download one real file end to end **inside the artifact**, with no display (`T321-R1`).

    The clean-machine evidence for `T-321` was a launch, four probes and the release gates — and
    **not a real download**, because that needed the GUI driven and had no headless route. So the
    one thing a clean machine is uniquely able to disprove went unasked: that this bundle can
    reach a real site, over TLS, with its own certificates, and write a file. Every previous real
    download was taken on a machine that already had Python, Qt and a system yt-dlp installed.

    **This calls `run_session`, the same function the spawned worker runs.** Not a parallel
    implementation and not the GUI: yt-dlp is resolved the way a job resolves it, the extractor
    runs, the bytes land through the real writer. `MessageSink` is a `Protocol` precisely so the
    caller can be a plain queue rather than an IPC one.

    **What this does not cover, stated rather than implied.** It does not spawn a child — that is
    `--spawn-probe`'s question and it is asked separately — and it drives no widget, so the
    dialog-to-queue wiring is not exercised here. `TESTING` §8 item 8's *cancel another* is
    likewise not covered: cancellation is a parent-side signal, and this probe has no parent.
    """
    import queue as queue_module
    import tempfile

    from tracks_and_trails.core.models import DownloadRequest
    from tracks_and_trails.downloader.protocol import (
        Failed,
        ResolutionReport,
        SessionKind,
        Succeeded,
    )
    from tracks_and_trails.downloader.worker import run_session

    target = url or DOWNLOAD_PROBE_URL
    say(f"url             {target}")

    with tempfile.TemporaryDirectory(prefix="tt-download-probe-") as directory:
        request = DownloadRequest(
            url=target,
            output_directory=directory,
            # A direct media file declares no height, so the height-filtered default legitimately
            # matches nothing — the same reasoning `tests/network/test_real_download.py` records
            # for choosing its preset.
            format_selector="best",
            output_template="%(title)s.%(ext)s",
        )
        messages: queue_module.Queue[Any] = queue_module.Queue()
        started = time.monotonic()
        try:
            run_session(SessionKind.DOWNLOAD, "download-probe", request, messages)
        except Exception as error:  # a probe reports; it does not raise out of the artifact
            say(f"FAIL: the download session raised: {error!r}", error=True)
            return 1
        elapsed = time.monotonic() - started

        outcome: Succeeded | Failed | None = None
        while True:
            try:
                message = messages.get_nowait()
            except queue_module.Empty:
                break
            if isinstance(message, ResolutionReport):
                say(f"yt-dlp          {message.ytdlp_version} from {message.ytdlp_source}")
            elif isinstance(message, Succeeded | Failed):
                outcome = message

        if isinstance(outcome, Failed):
            say(f"FAIL: the download failed as {outcome.kind}: {outcome.message}", error=True)
            return 1
        if outcome is None:
            say(
                "FAIL: the session ended without an outcome, which is a protocol violation "
                "rather than a failed download (REQ-028).",
                error=True,
            )
            return 1

        produced = Path(outcome.output_path)
        if not produced.is_file():
            say(
                f"FAIL: the session reported success and {produced} is not a file. A download "
                f"that reports a path it did not write is worse than one that fails.",
                error=True,
            )
            return 1
        size = produced.stat().st_size
        if size == 0:
            say(f"FAIL: {produced.name} is empty.", error=True)
            return 1
        say(f"downloaded      {produced.name}, {size} bytes in {elapsed:.1f}s")

    say("download        ok")
    return 0
