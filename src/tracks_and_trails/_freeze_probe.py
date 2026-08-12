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
from multiprocessing.queues import Queue as QueueType
from pathlib import Path
from typing import Any

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

    child.start()
    try:
        payload = queue.get(timeout=TIMEOUT_SECONDS)
    # Any failure at all is a probe failure; there is no exception here worth re-raising.
    except Exception as exc:
        child.terminate()
        child.join(timeout=TIMEOUT_SECONDS)
        print(f"FAIL: no message from the spawned child: {exc!r}", file=sys.stderr)
        return 1
    finally:
        child.join(timeout=TIMEOUT_SECONDS)

    print(f"frozen           {is_frozen()}")
    print(f"parent pid       {os.getpid()}")
    print(f"child pid        {payload.get('pid')}")
    print(f"child frozen     {payload.get('frozen')}")
    print(f"message          {payload.get('message')}")
    print(f"child exitcode   {child.exitcode}")

    if payload.get("message") != PROBE_MESSAGE:
        print(f"FAIL: unexpected message {payload!r}", file=sys.stderr)
        return 1
    if payload.get("pid") == os.getpid():
        print("FAIL: the worker ran in the parent process; no child was spawned", file=sys.stderr)
        return 1
    if child.is_alive():
        print("FAIL: the child is still alive after join; it would be orphaned", file=sys.stderr)
        return 1
    if child.exitcode != 0:
        print(f"FAIL: child exited {child.exitcode}", file=sys.stderr)
        return 1

    print("OK: spawned a child from this build, exchanged one message, and reaped it")
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
        print(f"FAIL: no usable yt-dlp in the frozen artifact: {error}", file=sys.stderr)
        return 1

    print(f"ytdlp version   {resolved.version}")
    print(f"ytdlp source    {resolved.source}")
    print(f"ytdlp pin       {BASELINE_YTDLP_VERSION}")

    # `T033-R1`: the first acceptance criterion. Printing the version is not asserting it — a
    # stale or wrong yt-dlp passed every other check here, because "some yt-dlp with lots of
    # extractors" is exactly what a wrongly-pinned build also produces. `OPS-002` promises a
    # *pinned, tested* baseline, and this is the only place that promise is verifiable inside
    # the artifact.
    #
    # Compared normalised: the pin reads `2026.7.4` and the package reports `2026.07.04`.
    if normalise_version(resolved.version) != normalise_version(BASELINE_YTDLP_VERSION):
        print(
            f"FAIL: the artifact bundles yt-dlp {resolved.version}, but this build pins "
            f"{BASELINE_YTDLP_VERSION}. The frozen baseline is not the tested one (T-033, "
            "OPS-002).",
            file=sys.stderr,
        )
        return 1

    extractors = resolved.module.extractor.gen_extractor_classes()
    names = [cls.IE_NAME for cls in extractors]
    print(f"extractors      {len(names)}")

    # A handful of extractors is what you get when only the core was bundled. A real yt-dlp has
    # hundreds; the exact number changes upstream, so the bound is deliberately loose.
    if len(names) < 100:
        print(
            f"FAIL: only {len(names)} extractors resolved. The artifact carries yt-dlp's core "
            "without its extractors, so every URL would fail as if the site had changed "
            "(T-033).",
            file=sys.stderr,
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
        print(
            "FAIL: yt-dlp is present and reports extractors, but a known extractor could not "
            "be resolved by name. The lazy-extractor machinery did not survive freezing "
            "(T-033).",
            file=sys.stderr,
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
        print(
            f"FAIL: the extractor's real module could not be imported: {error}. The artifact "
            "carries yt-dlp's lazy extractor table but not the extractor code behind it, so "
            "every matching URL would fail as if the site had changed (T-033).",
            file=sys.stderr,
        )
        return 1

    real = type(extractor)
    print(f"resolved        {real.IE_NAME} from {real.__module__}")

    if "lazy" in real.__module__:
        print(
            f"FAIL: {real.IE_NAME} is still the lazy placeholder ({real.__module__}); the "
            "concrete extractor module was never loaded (T-033).",
            file=sys.stderr,
        )
        return 1

    # The stable, offline half of what an extractor does: decide whether it handles a URL. No
    # network — a packaging gate that needs the internet is a gate that fails on a bad day.
    if not real.suitable(_KNOWN_URL) or real.suitable(_UNRELATED_URL):
        print(
            f"FAIL: {real.IE_NAME} loaded but does not match its own URL pattern; the "
            "extractor code in this artifact is not the one it claims to be (T-033).",
            file=sys.stderr,
        )
        return 1

    # **Asked, not performed** (`T033-R5`). Where the solver lives, what it is called, which hash
    # vouches for it and how it is loaded are upstream's business and change when upstream changes
    # them — so they live behind `downloader/worker.py` with the rest of the yt-dlp coupling
    # (`ARCHITECTURE.md` §6). This module reads a `SolverReport` and decides an exit code, which
    # is all a probe should know.
    solver = bundled_solver(resolved.module)
    if not solver.usable:
        print(f"FAIL: {solver.problem} (T-033, T033-R4)", file=sys.stderr)
        return 1
    print(f"solver          {solver.name} v{solver.version}, hash verified")
    print(f"solver extras   {len(solver.also)} also present: {', '.join(solver.also) or '-'}")

    print("OK: the frozen artifact carries a usable yt-dlp with its extractors")
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
        print(f"FAIL: the migration directory is unusable: {error}", file=sys.stderr)
        return 1

    print(f"migrations      {len(migrations)}")
    if not migrations:
        print(
            "FAIL: the frozen artifact carries no migration SQL. The spec did not collect "
            "persistence/migrations/*.sql, so the database would be created empty and every "
            "write would fail with 'no such table' (T-014, T014-R3).",
            file=sys.stderr,
        )
        return 1

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "probe.sqlite3"
        try:
            with db.open_database(path) as connection:
                version = db.schema_version(connection)
                print(f"schema version  {version}")
                if version != db.latest_version():
                    print(
                        f"FAIL: the database came up at version {version}, expected "
                        f"{db.latest_version()}.",
                        file=sys.stderr,
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
                    print(
                        "FAIL: a job written inside the artifact did not read back.",
                        file=sys.stderr,
                    )
                    return 1
        except Exception as error:
            print(f"FAIL: the frozen artifact could not use its database: {error}", file=sys.stderr)
            return 1

    print("database        ok")
    return 0
