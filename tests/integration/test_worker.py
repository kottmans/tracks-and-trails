"""The spawned worker (`T-012`).

`docs/project/TESTING.md` §6: **the process boundary is never mocked here.** A real child process is
spawned, real messages cross a real queue, and the worker imports the real yt-dlp. What is
faked is the *network* — extraction is stubbed at the `ytdlp_adapter` seam or driven from the
recorded fixture, because a test that fails when a site changes teaches nothing about our code.

`ARC-002` is the bet this file exists to test: that a worker can run headless, in its own
interpreter, and report structured results back.
"""

import json
import multiprocessing as mp
import os
import subprocess
import sys
import textwrap
from dataclasses import replace
from pathlib import Path
from queue import Queue
from typing import Any

import pytest

from tests.capabilities import SymlinkCapability
from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.models import AudioCodec, DownloadRequest, MediaKind
from tracks_and_trails.core.paths import UnsafePathError, is_contained, safe_output_path
from tracks_and_trails.downloader import worker as worker_module
from tracks_and_trails.downloader.environment import FfmpegReport, ytdlp_candidates
from tracks_and_trails.downloader.protocol import (
    Failed,
    Probed,
    ResolutionReport,
    SessionKind,
    Succeeded,
    WorkerFinished,
    validate_sequence,
)

REPO_ROOT = Path(__file__).parents[2]


def request_for(tmp_path: Path, **overrides: Any) -> DownloadRequest:
    base: dict[str, Any] = {
        "url": "https://archive.org/details/BigBuckBunny_124",
        "output_directory": str(tmp_path),
        "format_selector": "best",
        "output_template": "%(title)s.%(ext)s",
    }
    return DownloadRequest(**{**base, **overrides})


def drain(queue: Queue[Any]) -> list[Any]:
    messages = []
    while not queue.empty():
        messages.append(queue.get_nowait())
    return messages


# --- import safety under spawn (ARC-002, ARCHITECTURE.md §3) --------------------------------


def test_importing_the_worker_performs_no_work() -> None:
    """Under `spawn`, Python re-imports the child's module in a fresh interpreter.

    Any work at import time therefore runs on *every* spawn — and in a frozen build it runs in
    a process that believes it is the application (`T-020`). Asserted in a fresh interpreter,
    because this one has already imported the module.
    """
    probe = textwrap.dedent(
        """
        import sys, json
        before = set(sys.modules)
        import tracks_and_trails.downloader.worker as w
        after = set(sys.modules)
        print(json.dumps({
            "imported_ytdlp": "yt_dlp" in after,
            "imported_qt": any(m.startswith("PySide6") for m in after),
            "new_modules": len(after - before),
        }))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, cwd=REPO_ROOT, check=True
    )
    facts = json.loads(result.stdout.strip().splitlines()[-1])
    assert not facts["imported_ytdlp"], "importing the worker must not import yt-dlp"
    assert not facts["imported_qt"], "the worker must inherit no Qt (ARC-002)"


#: The variables that make a display reachable on Linux. Removed rather than blanked: an empty
#: `DISPLAY` is a *different* condition from an absent one, and libraries branch on both.
DISPLAY_VARIABLES = ("DISPLAY", "WAYLAND_DISPLAY")


def test_the_worker_really_runs_with_no_display_attached() -> None:
    """Phase 1's sixth exit criterion, enforced rather than assumed (`P1EXIT-R1`).

    **What this replaces was not a headless test.** The exit criterion is *worker code runs with
    no display attached*, and the evidence offered for it was the layering test plus
    `QT_QPA_PLATFORM=offscreen`. Neither establishes it. The layering test is a static import
    guard — it proves `worker.py` does not *import* Qt, which is a different claim. And offscreen
    selects a platform plugin; it does not remove the display. Every worker test in this file
    inherits `os.environ`, so `DISPLAY` has been present in all of them, including the one whose
    docstring says "the worker runs with no display".

    So this scrubs the variables and checks inside the child that they are actually gone, because
    a headless test that silently kept its display would be the vacuous gate `T-026` exists to
    prevent — and this one would have looked identical to the real thing.

    It does real work rather than importing: resolving yt-dlp is the first thing a spawned session
    does, and a display dependency in that path is exactly what would break a worker on a headless
    machine.
    """
    probe = textwrap.dedent(
        """
        import json, os, pathlib, sys

        seen = {name: os.environ.get(name) for name in ("DISPLAY", "WAYLAND_DISPLAY")}

        from tracks_and_trails.downloader.environment import ytdlp_candidates
        from tracks_and_trails.downloader.worker import _import_ytdlp

        resolved = _import_ytdlp(ytdlp_candidates(None))

        print(json.dumps({
            "display": seen,
            "resolved": bool(resolved),
            "imported_qt": any(m.startswith("PySide6") for m in sys.modules),
        }))
        """
    )
    environment = {k: v for k, v in os.environ.items() if k not in DISPLAY_VARIABLES}
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=True,
        env=environment,
    )
    facts = json.loads(result.stdout.strip().splitlines()[-1])

    # The guard against a vacuous pass: if the child could still see a display, everything below
    # it proves nothing about running without one.
    assert facts["display"] == {"DISPLAY": None, "WAYLAND_DISPLAY": None}, (
        f"the child still had a display: {facts['display']}. This test cannot say anything "
        f"about headless operation until that is empty."
    )
    assert facts["resolved"], "the worker could not resolve yt-dlp with no display attached"
    assert not facts["imported_qt"], "the worker inherited Qt (ARC-002)"


def test_the_worker_imports_no_qt_even_transitively() -> None:
    """`ARC-002`: the worker must not pull Qt in through a helper.

    A static import guard, and only that. *Running* with no display is
    `test_the_worker_really_runs_with_no_display_attached` — this one inherits the environment,
    display included, which is why it cannot stand in for that criterion (`P1EXIT-R1`).
    """
    probe = (
        "import tracks_and_trails.downloader.worker, sys; "
        "print(any(m.startswith('PySide6') for m in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, cwd=REPO_ROOT, check=True
    )
    assert result.stdout.strip() == "False"


# --- yt-dlp resolution and the loud fallback (OPS-002, ARCHITECTURE.md §6) -------------------


def _resolve_in_fresh_interpreter(user_directory: Path) -> dict[str, Any]:
    """Run `_import_ytdlp` in a **clean** interpreter and return what it reported.

    A subprocess is not incidental here. This interpreter has already imported yt-dlp, so
    `import yt_dlp` returns the cached module without consulting `sys.path` and the user
    candidate is never actually attempted — in-process, the fallback cannot be observed at all.
    A spawned worker starts clean, which is the condition these tests are about.

    The probe also classifies a transport error *after* resolving, because `T012-R2`'s real
    damage was to class identity: a fallback that leaves half-initialised modules behind can
    return a working module whose exception classes are not the ones the adapter binds.
    """
    probe = textwrap.dedent(
        """
        import json, pathlib, sys
        from tracks_and_trails.downloader.environment import ytdlp_candidates
        from tracks_and_trails.downloader.worker import _import_ytdlp

        resolved = _import_ytdlp(ytdlp_candidates(pathlib.Path(sys.argv[1])))

        from tracks_and_trails.downloader import ytdlp_adapter as adapter
        from tracks_and_trails.core.errors import ErrorKind
        from yt_dlp.networking.exceptions import ProxyError

        kind = adapter.classify_exception(ProxyError("proxy refused")).kind
        print(json.dumps({
            "version": resolved.version,
            "source": resolved.source,
            "rejected": list(resolved.rejected),
            "classified": kind.value,
            "network": ErrorKind.NETWORK.value,
        }))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", probe, str(user_directory)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=True,
    )
    return dict(json.loads(result.stdout.strip().splitlines()[-1]))


#: Broken user copies, by the shape of their failure. Each is a real `__init__.py` body.
#:
#: `partial-import` is `T012-R2`'s reproduction and the reason this is a table: the package
#: imports one of its own submodules *before* failing, leaving `yt_dlp.version` behind in
#: `sys.modules`. The baseline attempt then reused that stale submodule and died with
#: `cannot import name 'CHANNEL'` — so a broken override took the baseline down with it.
#:
#: The last two are not `ImportError` at all. A user copy is arbitrary third-party code, and
#: catching only `ImportError` meant those shapes killed the worker instead of falling back.
BROKEN_SHAPES: dict[str, str] = {
    "clean-raise": "raise ImportError('deliberately broken')\n",
    "partial-import": (
        "import yt_dlp.version\nraise ImportError('broken after importing a submodule')\n"
    ),
    "syntax-error": "def (\n",
    "runtime-error": "raise RuntimeError('not an ImportError at all')\n",
    # Embeds its own location in the message, which many real packages do. This is the shape
    # that makes `NFR-007` redaction observable — the others carry no path to leak.
    "path-in-message": "raise ImportError('failed loading ' + __file__)\n",
    # `SystemExit` is not an `Exception`, so it escaped the candidate boundary entirely and the
    # baseline was never tried — a broken override taking the whole worker down with it. Real
    # packages do call `sys.exit()` at import time on a failed environment check.
    "system-exit": "import sys\nsys.exit('broken override exited during import')\n",
    # Neither is a bare `BaseException`. §6's rule is about importing cleanly, not about which
    # base class the failure chose.
    "base-exception": "raise BaseException('not even an Exception')\n",
}


@pytest.mark.parametrize("shape", sorted(BROKEN_SHAPES))
def test_a_broken_user_copy_falls_back_to_the_baseline_and_says_so(
    tmp_path: Path, shape: str
) -> None:
    """An acceptance criterion, and the one §6 is emphatic about.

    A user who installs a broken copy and silently gets the baseline's behaviour has been lied
    to. The fallback must happen **and** be reported — for every way a copy can be broken, not
    only the tidiest one.
    """
    broken = tmp_path / "ytdlp"
    package = broken / "yt_dlp"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(BROKEN_SHAPES[shape])
    # A submodule the partial-import shape can import before it fails.
    (package / "version.py").write_text("__version__ = '0.0.0-broken'\n")

    facts = _resolve_in_fresh_interpreter(broken)

    assert facts["version"], "the baseline should still have been imported"
    assert facts["version"] != "0.0.0-broken", "the broken copy was used, not the baseline"
    assert "baseline" in facts["source"]
    assert facts["rejected"], "the rejected candidate must be reported, not silently skipped"


@pytest.mark.parametrize("shape", sorted(BROKEN_SHAPES))
def test_the_taxonomy_survives_a_fallback(tmp_path: Path, shape: str) -> None:
    """`T012-R2`: falling back must not leave the adapter binding classes from a dead module.

    A fallback that "succeeds" while `sys.modules` still holds the broken copy's submodules can
    hand back a module whose exception classes are not the ones `ytdlp_adapter` compares
    against — and every failure would then classify as `EXTRACTOR_ERROR`. Classification is
    asserted after the fallback for exactly that reason.
    """
    broken = tmp_path / "ytdlp"
    package = broken / "yt_dlp"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(BROKEN_SHAPES[shape])
    (package / "version.py").write_text("__version__ = '0.0.0-broken'\n")

    facts = _resolve_in_fresh_interpreter(broken)

    assert facts["classified"] == facts["network"], (
        "after falling back, a transport error no longer classifies as NETWORK — "
        "the adapter is bound to classes from the discarded copy"
    )


def test_the_reported_source_is_derived_from_what_was_loaded(tmp_path: Path) -> None:
    """The worker must not claim a source it did not use.

    In this interpreter yt-dlp is already imported, so a user-copy candidate cannot actually
    win — and the report says so rather than repeating the candidate label. Reporting the
    attempted candidate would make `OPS-002`'s guarantee unfalsifiable.
    """
    user_copy = tmp_path / "ytdlp"
    user_copy.mkdir()

    resolved = worker_module._import_ytdlp(ytdlp_candidates(user_copy))

    assert "already-imported" in resolved.source or "baseline" in resolved.source


def test_the_resolved_version_is_read_from_the_module_not_a_recorded_string() -> None:
    """`REQ-025`. A recorded string would drift from what actually ran."""
    import yt_dlp

    resolved = worker_module._import_ytdlp(ytdlp_candidates(None))
    assert resolved.version == yt_dlp.version.__version__


def test_a_completely_unimportable_ytdlp_raises_rather_than_returning_nothing() -> None:
    """No candidate importing means the application is broken, not the user's copy."""
    with pytest.raises(ImportError, match="no usable yt-dlp"):
        worker_module._import_ytdlp(())


# --- session outcomes (T-011's grammar) -------------------------------------------------------


def fake_extract(info: dict[str, Any], *, produces: str | None = None) -> Any:
    """Replace extraction with a recorded result, leaving the rest of the worker real.

    **A download that reports success also writes a file** (`T046-R1`). It did not until then, and
    the worker tolerated it because the *reservation* was the file — so every fake here claimed a
    successful download that had produced nothing, and `T-077`'s lesson (four of five options never
    produced a file) was reproduced in the harness itself.

    `produces` overrides the written name when a postprocessor would have changed the extension,
    which is the case the reservation never covered. Left `None`, the file is written at the name
    the worker asked for.
    """

    def _extract(
        _adapter: Any,
        _request: Any,
        _resolved: Any,
        _reporter: Any,
        *,
        probe_only: bool,
        output_template: str | None = None,
        **_extra: Any,
    ) -> dict[str, Any]:
        result = dict(info)
        if not probe_only and output_template is not None:
            asked = Path(output_template)
            written = asked if produces is None else asked.with_name(produces)
            written.parent.mkdir(parents=True, exist_ok=True)
            written.write_bytes(b"fake media")
            result.setdefault("requested_downloads", [{"filepath": str(written)}])
        return result

    return _extract


def test_a_probe_session_emits_probed_then_the_sentinel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The `T011-R1` shape: a successful probe is a complete session with one outcome."""
    from tests.unit.test_ytdlp_adapter import load_fixture

    monkeypatch.setattr(worker_module, "_extract", fake_extract(load_fixture()))
    queue: Queue[Any] = Queue()

    code = worker_module.run_session(SessionKind.PROBE, "job-1", request_for(tmp_path), queue)

    messages = drain(queue)
    assert code == 0
    validate_sequence(SessionKind.PROBE, messages)
    assert isinstance(messages[-1], WorkerFinished)
    assert any(isinstance(m, Probed) for m in messages)


def test_a_probe_of_the_fixture_yields_the_expected_media(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.test_ytdlp_adapter import load_fixture

    info = load_fixture()
    monkeypatch.setattr(worker_module, "_extract", fake_extract(info))
    queue: Queue[Any] = Queue()
    worker_module.run_session(SessionKind.PROBE, "job-1", request_for(tmp_path), queue)

    probed = next(m for m in drain(queue) if isinstance(m, Probed))
    assert probed.media.title == info["title"]
    assert len(probed.media.formats) == len(info["formats"])


def test_a_failure_reaches_the_parent_classified_and_verbatim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`REQ-018`, `NFR-006`: never fail silently, never paraphrase."""
    from yt_dlp.utils import GeoRestrictedError

    def explode(*_args: Any, **_kwargs: Any) -> Any:
        raise GeoRestrictedError("This video is not available in your country")

    monkeypatch.setattr(worker_module, "_extract", explode)
    queue: Queue[Any] = Queue()

    code = worker_module.run_session(SessionKind.DOWNLOAD, "job-1", request_for(tmp_path), queue)

    messages = drain(queue)
    assert code == 1
    validate_sequence(SessionKind.DOWNLOAD, messages)
    failed = next(m for m in messages if isinstance(m, Failed))
    assert failed.kind is ErrorKind.GEO_RESTRICTED
    assert failed.message == "This video is not available in your country"


def test_an_unsupported_url_fails_the_job_with_the_extractors_own_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Phase 1's fifth exit criterion, with the error class the criterion is about (`P1EXIT-R2`).

    The criterion is *an unsupported URL produces a failed job showing the extractor's own
    message*. The evidence offered for it was
    `test_a_failure_reaches_the_parent_classified_and_verbatim`, which raises `GeoRestrictedError`
    and asserts `GEO_RESTRICTED` — a real session and a real assertion about a **different**
    failure. Citing it repeated the mapping defect it was meant to correct, one error class over.

    `UnsupportedError` is what yt-dlp raises for a URL no extractor claims, and
    `ytdlp_adapter`'s table maps it to `UNSUPPORTED_URL` *before* the `ExtractorError` entry it
    subclasses — order that is load-bearing and worth exercising from the session end.

    **Still honest about its limit:** the error is injected at the `_extract` seam rather than
    produced by sending a genuinely unsupported URL through yt-dlp. What this proves is that such
    an error is classified correctly and carried verbatim to the parent; what it does not prove is
    yt-dlp's own recognition of the URL.
    """
    from yt_dlp.utils import UnsupportedError

    # `UnsupportedError` takes the **URL**, not a message, and writes the sentence itself.
    # Constructing it with a ready-made message produces "Unsupported URL: Unsupported URL: ..."
    # — which this test caught on its first run, and which is a small demonstration that the
    # message really is carried through untouched rather than rebuilt on our side.
    url = "https://example.invalid/nothing-here"
    text = f"Unsupported URL: {url}"

    def unsupported(*_args: Any, **_kwargs: Any) -> Any:
        raise UnsupportedError(url)

    monkeypatch.setattr(worker_module, "_extract", unsupported)
    queue: Queue[Any] = Queue()

    code = worker_module.run_session(SessionKind.DOWNLOAD, "job-1", request_for(tmp_path), queue)

    messages = drain(queue)
    assert code == 1
    validate_sequence(SessionKind.DOWNLOAD, messages)
    failed = next(m for m in messages if isinstance(m, Failed))
    assert failed.kind is ErrorKind.UNSUPPORTED_URL, (
        f"an unsupported URL was classified {failed.kind}. `UnsupportedError` subclasses "
        f"`ExtractorError`, so a table that checks the parent first silently answers "
        f"EXTRACTOR_ERROR here."
    )
    assert failed.message == text, "the extractor's own message did not survive verbatim"


def test_every_session_ends_with_the_sentinel_even_when_everything_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without it the parent blocks on `Queue.get()` forever (`ARCHITECTURE.md` §3)."""

    def explode(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("something nobody anticipated")

    monkeypatch.setattr(worker_module, "_import_ytdlp", explode)
    queue: Queue[Any] = Queue()

    worker_module.run_session(SessionKind.PROBE, "job-1", request_for(tmp_path), queue)

    messages = drain(queue)
    assert isinstance(messages[-1], WorkerFinished)
    assert isinstance(messages[0], Failed)


# --- DRM (REQ-EXCL-001, SEC-001) --------------------------------------------------------------


def test_a_drm_item_fails_without_attempting_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The acceptance criterion: classified non-retryable, and **no alternative attempted**.

    Asserted by counting extraction calls: a download session probes once and must stop there.
    A second call would be an attempt to find a way around the protection.
    """
    calls: list[bool] = []

    def counting_extract(
        _a: Any,
        _r: Any,
        _res: Any,
        _rep: Any,
        *,
        probe_only: bool,
        output_template: str | None = None,
        **_extra: Any,
    ) -> dict[str, Any]:
        calls.append(probe_only)
        return {"_has_drm": True, "title": "Protected", "webpage_url": "https://e.com/x"}

    monkeypatch.setattr(worker_module, "_extract", counting_extract)
    queue: Queue[Any] = Queue()

    worker_module.run_session(SessionKind.DOWNLOAD, "job-1", request_for(tmp_path), queue)

    failed = next(m for m in drain(queue) if isinstance(m, Failed))
    assert failed.kind is ErrorKind.DRM_PROTECTED
    assert calls == [True], "extraction was retried after DRM was detected"


# --- ffmpeg (REQ-024, OPS-001) ----------------------------------------------------------------


def test_a_merge_without_ffmpeg_fails_before_downloading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`REQ-024`'s whole point: told up front, not after the bandwidth is spent."""
    calls: list[bool] = []

    def counting_extract(
        _a: Any,
        _r: Any,
        _res: Any,
        _rep: Any,
        *,
        probe_only: bool,
        output_template: str | None = None,
        **_extra: Any,
    ) -> dict[str, Any]:
        calls.append(probe_only)
        # **States the fact, not the selector** (`T-061`). This returned `{"formats": []}`, which
        # resolves to nothing, so the gate fell back to reading `+` out of the selector and this
        # test passed without exercising the merge path at all. `requested_formats` with two
        # entries is yt-dlp's own record that it will merge.
        return {
            "title": "Clip",
            "webpage_url": "https://e.com/x",
            "formats": [],
            "requested_formats": [{"format_id": "v"}, {"format_id": "a"}],
        }

    monkeypatch.setattr(worker_module, "_extract", counting_extract)
    monkeypatch.setattr(
        worker_module,
        "find_ffmpeg",
        lambda **_: FfmpegReport(
            path=None, source="not found on PATH", unavailable_features=("merging",)
        ),
    )
    queue: Queue[Any] = Queue()

    worker_module.run_session(
        SessionKind.DOWNLOAD,
        "job-1",
        request_for(tmp_path, format_selector="bestvideo+bestaudio"),
        queue,
    )

    failed = next(m for m in drain(queue) if isinstance(m, Failed))
    assert failed.kind is ErrorKind.FFMPEG_MISSING
    assert calls == [True], "the download proceeded despite ffmpeg being unavailable"


def test_a_plain_download_without_ffmpeg_is_not_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only formats that *need* ffmpeg are gated; a single-file download is fine without it."""
    monkeypatch.setattr(
        worker_module,
        "find_ffmpeg",
        lambda **_: FfmpegReport(path=None, source="absent"),
    )
    monkeypatch.setattr(
        worker_module,
        "_extract",
        # `format_id` is what says a single format satisfied the selection (`T-061`).
        fake_extract(
            {
                "title": "Clip",
                "webpage_url": "https://e.com/x",
                "ext": "mp4",
                "format_id": "mp4",
            }
        ),
    )
    monkeypatch.setattr(worker_module, "_validated_target", lambda *a, **k: tmp_path / "Clip.mp4")
    queue: Queue[Any] = Queue()

    worker_module.run_session(
        SessionKind.DOWNLOAD, "job-1", request_for(tmp_path, format_selector="best"), queue
    )

    assert any(isinstance(m, Succeeded) for m in drain(queue))


# --- the preview tells the truth (REQ-011) ----------------------------------------------------


def test_the_preview_equals_the_path_the_download_actually_uses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`REQ-011`'s acceptance criterion: render, preview, and compare.

    A preview is a promise about where the file will land. If it is computed by a different
    route than the write, the two drift and the user is told one location while another is
    written — silently, and only for the titles where the routes happen to disagree.

    So this does not compare `preview_path` against the helper it calls, which would pass
    however wrong both were (`docs/project/TESTING.md` §13). It takes the preview, then runs a real
    download session and reads the path out of the `Succeeded` message the parent would
    receive. The two must agree, having been observed through different paths.

    The title is a **reserved device name**, chosen after a first attempt using `: " ?` proved
    vacuous: yt-dlp's own `prepare_filename` already maps those to fullwidth forms, so `T-034`
    had nothing left to change and a preview that skipped sanitisation entirely still matched.
    Reserved names are a case yt-dlp does not handle and `T-045` defuses with a digest, so the
    two routes genuinely diverge — on every platform, not only on Windows.
    """
    info = {"title": "CON", "webpage_url": "https://e.com/x", "ext": "mp4"}
    resolved = worker_module._import_ytdlp(ytdlp_candidates(None))
    request = request_for(tmp_path, format_selector="best")

    preview = worker_module.preview_path(request, dict(info), resolved)

    # Stands in for yt-dlp: reports back the very template it was handed, which is what a
    # real single-file download does.
    def extract_reporting_its_target(
        _a: Any,
        _r: Any,
        _res: Any,
        _rep: Any,
        *,
        probe_only: bool,
        output_template: str | None = None,
        **_extra: Any,
    ) -> dict[str, Any]:
        if probe_only:
            return dict(info)
        # Writes what it reports (`T046-R1`): the claim moves the produced file, so a download
        # that reports a path it never wrote is now correctly a failure rather than a success.
        assert output_template is not None
        written = Path(output_template)
        written.parent.mkdir(parents=True, exist_ok=True)
        written.write_bytes(b"fake media")
        return {**info, "requested_downloads": [{"filepath": output_template}]}

    monkeypatch.setattr(worker_module, "_extract", extract_reporting_its_target)
    monkeypatch.setattr(
        worker_module, "find_ffmpeg", lambda **_: FfmpegReport(path=None, source="absent")
    )
    queue: Queue[Any] = Queue()

    worker_module.run_session(SessionKind.DOWNLOAD, "job-1", request, queue)

    succeeded = next(m for m in drain(queue) if isinstance(m, Succeeded))
    assert succeeded.output_path == str(preview)
    assert Path(succeeded.output_path).parent == tmp_path, (
        "the preview and the write agreed, but on a location outside the chosen directory"
    )


def test_the_worker_hands_yt_dlp_the_ffmpeg_it_gated_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T012-R5`/`OPS-001`: resolving ffmpeg and then not telling yt-dlp is worse than not
    resolving it.

    The worker checks a specific binary exists and lets the download proceed on that basis. If
    the path never reaches `YoutubeDL`, yt-dlp runs its own lookup and may use a different
    ffmpeg — or none — so the gate the user passed was about a binary that was never used.

    Written because a mutation replacing the forwarded path with `None` left the whole suite
    green: `build_options` was tested for accepting the argument, but nothing checked that the
    worker supplied it.
    """
    resolved_ffmpeg = tmp_path / "bin" / "ffmpeg"
    resolved_ffmpeg.parent.mkdir()
    resolved_ffmpeg.touch()
    seen: list[Any] = []

    def capturing_extract(
        _a: Any,
        _r: Any,
        _res: Any,
        _rep: Any,
        *,
        probe_only: bool,
        output_template: str | None = None,
        ffmpeg_location: Any = None,
        **_extra: Any,
    ) -> dict[str, Any]:
        if not probe_only:
            seen.append(ffmpeg_location)
        return {"title": "Clip", "webpage_url": "https://e.com/x", "ext": "mp4"}

    monkeypatch.setattr(worker_module, "_extract", capturing_extract)
    monkeypatch.setattr(
        worker_module,
        "find_ffmpeg",
        lambda **_: FfmpegReport(path=resolved_ffmpeg, source="resolved for the test"),
    )
    queue: Queue[Any] = Queue()

    worker_module.run_session(
        SessionKind.DOWNLOAD, "job-1", request_for(tmp_path, format_selector="best"), queue
    )

    assert seen == [resolved_ffmpeg], "the download did not receive the gated ffmpeg path"


def test_a_keyboard_interrupt_during_resolution_is_not_swallowed(tmp_path: Path) -> None:
    """The one interruption that must **not** become a fallback (`T012-R2`).

    Widening the candidate boundary to `BaseException` is right for a third-party module that
    fails to import, but `KeyboardInterrupt` does not mean "this copy is broken" — it means the
    user asked this process to stop. Falling back and carrying on would ignore them, and would
    do so invisibly, since the baseline usually imports fine.
    """
    broken = tmp_path / "ytdlp"
    package = broken / "yt_dlp"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("raise KeyboardInterrupt('user pressed ctrl-c')\n")

    # Fresh interpreter for the same reason as the fallback matrix: in this one yt-dlp is
    # already imported, so the broken candidate is never attempted and nothing would be raised.
    probe = textwrap.dedent(
        """
        import pathlib, sys

        from tracks_and_trails.downloader.environment import ytdlp_candidates
        from tracks_and_trails.downloader.worker import _import_ytdlp

        try:
            _import_ytdlp(ytdlp_candidates(pathlib.Path(sys.argv[1])))
        except KeyboardInterrupt:
            print("PROPAGATED")
        else:
            print("SWALLOWED")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", probe, str(broken)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=True,
    )

    assert result.stdout.strip().splitlines()[-1] == "PROPAGATED", (
        "a user interrupt was treated as a broken candidate and silently fell back"
    )


# --- what the parent actually learns (T012-R1, REQ-025) --------------------------------------


def test_a_successful_session_reports_which_ytdlp_it_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`REQ-025`: the resolved version must reach the **parent**, not just the worker.

    This is asserted through `run_session` on purpose. The previous tests read `ResolvedYtdlp`
    directly, so they passed while a successful probe emitted only `Progress`, `Probed` and the
    sentinel — the version was computed correctly and thrown away. A fact the parent cannot
    observe is not reported (`docs/project/TESTING.md` §13).
    """
    from tests.unit.test_ytdlp_adapter import load_fixture

    monkeypatch.setattr(worker_module, "_extract", fake_extract(load_fixture()))
    queue: Queue[Any] = Queue()

    worker_module.run_session(SessionKind.PROBE, "job-1", request_for(tmp_path), queue)
    messages = drain(queue)

    report = next(m for m in messages if isinstance(m, ResolutionReport))
    assert report.ytdlp_version == _resolved().version
    assert report.ytdlp_source
    validate_sequence(SessionKind.PROBE, messages)


def test_a_successful_download_also_reports_its_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both outcome types, since the report describes the environment rather than the result."""
    info = {"title": "Clip", "webpage_url": "https://e.com/x", "ext": "mp4"}
    messages = _run_download(tmp_path, monkeypatch, info)

    assert any(isinstance(m, Succeeded) for m in messages)
    assert any(isinstance(m, ResolutionReport) for m in messages)
    validate_sequence(SessionKind.DOWNLOAD, messages)


def test_the_report_precedes_the_outcome(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A report arriving after the outcome could not inform how the outcome is interpreted."""
    from tests.unit.test_ytdlp_adapter import load_fixture

    monkeypatch.setattr(worker_module, "_extract", fake_extract(load_fixture()))
    queue: Queue[Any] = Queue()

    worker_module.run_session(SessionKind.PROBE, "job-1", request_for(tmp_path), queue)
    messages = drain(queue)

    kinds = [type(m).__name__ for m in messages]
    assert kinds.index("ResolutionReport") < kinds.index("Probed")


def test_a_successful_fallback_tells_the_parent_what_was_rejected(tmp_path: Path) -> None:
    """The other half of the broken-override criterion: the fallback must "say so" *to the
    parent*.

    Run in a spawned process because a fallback cannot happen in an interpreter that has already
    imported yt-dlp, and asserted on the queue because the worker's own local variable was never
    the thing the criterion was about (`ARCHITECTURE.md` §6).
    """
    broken = tmp_path / "ytdlp"
    package = broken / "yt_dlp"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("raise ImportError('deliberately broken')\n")

    context = mp.get_context("spawn")
    queue: Any = context.Queue()
    process = context.Process(
        target=_report_target, args=(queue, str(tmp_path / "out"), str(broken))
    )
    (tmp_path / "out").mkdir()
    process.start()
    process.join(timeout=120)

    messages = []
    while not queue.empty():
        messages.append(queue.get_nowait())

    report = next(m for m in messages if isinstance(m, ResolutionReport))
    assert report.rejected, "the rejected override never reached the parent"
    assert "baseline" in report.ytdlp_source


def test_the_rejection_reason_carries_no_filesystem_path(tmp_path: Path) -> None:
    """`NFR-007`: the reason travels to the parent and is logged, so it carries a label.

    The user configured the directory; repeating its absolute path back tells them nothing and
    puts a local path into records that persist.
    """
    broken = tmp_path / "ytdlp"
    package = broken / "yt_dlp"
    package.mkdir(parents=True)
    # Deliberately the shape that puts its own absolute path in the message. Using a failure
    # whose text contains no path would let this test pass with redaction removed entirely.
    (package / "__init__.py").write_text(BROKEN_SHAPES["path-in-message"])

    facts = _resolve_in_fresh_interpreter(broken)

    assert facts["rejected"]
    assert any("yt_dlp" in reason for reason in facts["rejected"]), (
        "the reason no longer names what failed; this test would pass vacuously"
    )
    for reason in facts["rejected"]:
        assert str(broken) not in reason, f"the candidate path leaked into: {reason!r}"


@pytest.mark.parametrize(
    ("overrides", "gated"),
    [
        ({"post_processors": ("FFmpegMetadata",)}, True),
        ({"post_processors": ("EmbedThumbnail",)}, True),
        ({"subtitle_languages": ("en",), "embed_subtitles": True}, True),
        ({"media_kind": MediaKind.AUDIO, "format_selector": "bestaudio"}, True),
        ({"format_selector": "bestvideo+bestaudio"}, True),
        ({"post_processors": ("Exec",)}, False),
        ({}, False),
    ],
)
def test_the_ffmpeg_gate_covers_every_processor_that_needs_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, overrides: dict[str, Any], gated: bool
) -> None:
    """`REQ-024`: told up front, not after the bandwidth is spent (`T012-R5`).

    The gate previously checked two flags — audio kind and subtitle embedding — so a request
    naming `FFmpegMetadata` or `EmbedThumbnail` passed it and then failed at post-processing,
    with the whole download already paid for.

    `Exec` is the control: it is a real post-processor that does **not** subclass
    `FFmpegPostProcessor`, so a gate that simply answered "yes" to any named processor would
    fail this row.
    """
    calls: list[bool] = []

    def counting_extract(
        _a: Any,
        _r: Any,
        _res: Any,
        _rep: Any,
        *,
        probe_only: bool,
        output_template: str | None = None,
        **_extra: Any,
    ) -> dict[str, Any]:
        calls.append(probe_only)
        return {"title": "Clip", "webpage_url": "https://e.com/x", "ext": "mp4"}

    monkeypatch.setattr(worker_module, "_extract", counting_extract)
    monkeypatch.setattr(
        worker_module,
        "find_ffmpeg",
        lambda **_: FfmpegReport(path=None, source="not found on PATH"),
    )
    queue: Queue[Any] = Queue()

    worker_module.run_session(
        SessionKind.DOWNLOAD, "job-1", request_for(tmp_path, **overrides), queue
    )
    messages = drain(queue)

    if gated:
        failed = next(m for m in messages if isinstance(m, Failed))
        assert failed.kind is ErrorKind.FFMPEG_MISSING
        assert calls == [True], "the download ran despite ffmpeg being unavailable"
    else:
        assert not any(
            isinstance(m, Failed) and m.kind is ErrorKind.FFMPEG_MISSING for m in messages
        ), "a download needing no ffmpeg was blocked"


# --- output template, containment and preview (T-034, REQ-011, T012-R4) ----------------------


def _resolved() -> Any:
    """The real yt-dlp, resolved the way the worker resolves it."""
    return worker_module._import_ytdlp(ytdlp_candidates(None))


def _run_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, info: dict[str, Any], **overrides: Any
) -> list[Any]:
    """Drive a real download session, faking only the network.

    Deliberately goes through `run_session` rather than calling `_validated_target` or
    `safe_output_path`. The previous tests called `paths` directly while claiming to test "the
    worker's own helper", so they passed whether or not the worker used the validated result at
    all — which is exactly how `T012-R4` survived (`docs/project/TESTING.md` §13).
    """

    def extract_reporting_its_target(
        _a: Any,
        _r: Any,
        _res: Any,
        _rep: Any,
        *,
        probe_only: bool,
        output_template: str | None = None,
        **_extra: Any,
    ) -> dict[str, Any]:
        if probe_only:
            return dict(info)
        # Stands in for yt-dlp: renders the template it was handed, as a real download does.
        rendered = (
            worker_module._import_ytdlp(ytdlp_candidates(None))
            .module.YoutubeDL({"outtmpl": output_template, "quiet": True})
            .prepare_filename(info)
        )
        # **And writes the file** (`T046-R1`). It did not before, and the worker did not notice
        # because the reservation was itself a file — so these tests asserted a successful download
        # that had produced nothing. The claim now moves what was produced, so producing nothing
        # is correctly a failure.
        written = Path(rendered)
        written.parent.mkdir(parents=True, exist_ok=True)
        written.write_bytes(b"fake media")
        return {**info, "requested_downloads": [{"filepath": rendered}]}

    monkeypatch.setattr(worker_module, "_extract", extract_reporting_its_target)
    monkeypatch.setattr(
        worker_module, "find_ffmpeg", lambda **_: FfmpegReport(path=None, source="absent")
    )
    queue: Queue[Any] = Queue()
    worker_module.run_session(
        SessionKind.DOWNLOAD,
        "job-1",
        # `format_selector` is a *default* here, not a fixture: spelling it as a keyword ahead of
        # `**overrides` made passing one a `TypeError` rather than an override, so the helper's
        # advertised contract did not hold for the one field a `T-050` test needs to vary.
        request_for(tmp_path, **{"format_selector": "best", **overrides}),
        queue,
    )
    return drain(queue)


def test_a_template_with_subdirectories_keeps_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T012-R4`: the user's template structure must survive validation.

    Reducing the rendered path to its filename discarded this silently — a template asking for
    `%(uploader)s/%(title)s.%(ext)s` wrote every file into one flat folder and never said so.
    """
    info = {"title": "Clip", "uploader": "Someone", "webpage_url": "https://e.com/x", "ext": "mp4"}
    messages = _run_download(
        tmp_path, monkeypatch, info, output_template="%(uploader)s/%(title)s.%(ext)s"
    )

    succeeded = next(m for m in messages if isinstance(m, Succeeded))
    written = Path(succeeded.output_path)
    assert written.parent.name == "Someone", "the template's subdirectory was discarded"
    assert written.parent.parent == tmp_path


@pytest.mark.parametrize(
    "template",
    [
        "../outside/%(title)s.%(ext)s",
        "../../outside/%(title)s.%(ext)s",
        # S108: the absolute path is the input under test — it must be refused, never used.
        "/tmp/outside/%(title)s.%(ext)s",  # noqa: S108
        "nested/../../outside/%(title)s.%(ext)s",
        "C:\\outside\\%(title)s.%(ext)s",
        "\\\\host\\share\\%(title)s.%(ext)s",
    ],
)
def test_a_template_that_renders_outside_is_rejected_not_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, template: str
) -> None:
    """The acceptance criterion, verbatim: "rejected, not written".

    Previously each of these was silently rewritten into the chosen directory, so the user was
    told their template worked when it had been discarded. Neutralising is right for a *title*
    the user did not choose; for a template they typed, it hides the mistake.
    """
    info = {"title": "Clip", "webpage_url": "https://e.com/x", "ext": "mp4"}
    messages = _run_download(tmp_path, monkeypatch, info, output_template=template)

    failed = next(m for m in messages if isinstance(m, Failed))
    assert failed.kind is ErrorKind.DISK
    assert not any(isinstance(m, Succeeded) for m in messages)
    assert list(tmp_path.rglob("*")) == [], "a file was written despite the template being rejected"


def test_a_title_that_looks_like_a_template_is_not_rendered_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T012-R4`: the validated path is handed to yt-dlp as data, not as a second template.

    A title containing `%(uploader)s` survived sanitisation as literal text; yt-dlp then
    expanded it on the second pass and wrote a *different* file than the one that was validated
    and previewed. Containment had been checked against a path that was never used.
    """
    info = {
        "title": "100% Real %(uploader)s",
        "uploader": "SOMEONE-ELSE",
        "webpage_url": "https://e.com/x",
        "ext": "mp4",
    }
    preview = worker_module.preview_path(
        request_for(tmp_path, format_selector="best"), dict(info), _resolved()
    )
    messages = _run_download(tmp_path, monkeypatch, info)

    succeeded = next(m for m in messages if isinstance(m, Succeeded))
    assert succeeded.output_path == str(preview), "the write drifted from the preview"
    assert "SOMEONE-ELSE" not in succeeded.output_path, (
        "the title was re-rendered as a template and picked up a second field"
    )


def test_a_traversal_title_lands_inside_the_output_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A hostile *title* is neutralised rather than rejected — it downloads, safely.

    The distinction from the rejection cases above is deliberate: the user chose the template,
    but the site chose the title.
    """
    info = {"title": "../../etc/passwd", "webpage_url": "https://e.com/x", "ext": "mp4"}
    messages = _run_download(tmp_path, monkeypatch, info)

    succeeded = next(m for m in messages if isinstance(m, Succeeded))
    assert is_contained(Path(succeeded.output_path), tmp_path)


def test_a_symlink_out_of_the_directory_is_still_refused(
    tmp_path: Path, symlinks: SymlinkCapability
) -> None:
    """`T-034`'s own guarantee, kept as a direct check because no template can express it."""
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    target = tmp_path / "Downloads"
    target.mkdir()
    symlinks.create(target / "link", outside)

    with pytest.raises(UnsafePathError):
        safe_output_path(target, "link/clip.mp4")


# --- a real spawned process (ARC-002) ---------------------------------------------------------


def _report_target(queue: Any, directory: str, user_ytdlp: str) -> None:
    """Runs in the child: a full session against a broken override, reporting on the queue."""
    from tracks_and_trails.core.models import DownloadRequest
    from tracks_and_trails.downloader import worker as w
    from tracks_and_trails.downloader.protocol import SessionKind

    w._extract = lambda *a, **k: {
        "title": "Spawned",
        "webpage_url": "https://e.com/x",
        "formats": [],
    }
    w.run_session(
        SessionKind.PROBE,
        "job-fallback",
        DownloadRequest(
            url="https://e.com/x",
            output_directory=directory,
            format_selector="best",
            output_template="%(title)s.%(ext)s",
        ),
        queue,
        user_ytdlp_directory=Path(user_ytdlp),
    )


def _spawn_target(queue: mp.Queue[Any], directory: str) -> None:
    """Runs in the child. Module-level so it is picklable under `spawn`.

    **The display check happens here, in the process that does the work** (`P1EXIT-R1`). Asserting
    it in the parent would prove only what the parent arranged; under `spawn` the child gets a
    fresh interpreter that inherits the environment, and this is the only place that inheritance
    can be observed. A failure here surfaces as a non-zero exit code, which the parent asserts.
    """
    import os as child_os

    still_visible = {
        name: child_os.environ[name]
        for name in ("DISPLAY", "WAYLAND_DISPLAY")
        if name in child_os.environ
    }
    if still_visible:
        raise AssertionError(
            f"the spawned worker inherited a display: {still_visible}. Everything this test "
            f"asserts below would then say nothing about running headless."
        )

    from tracks_and_trails.core.models import DownloadRequest
    from tracks_and_trails.downloader import worker as w
    from tracks_and_trails.downloader.protocol import SessionKind

    w._extract = lambda *a, **k: {
        "title": "Spawned",
        "webpage_url": "https://e.com/x",
        "formats": [],
    }
    w.run_session(
        SessionKind.PROBE,
        "job-spawn",
        DownloadRequest(
            url="https://e.com/x",
            output_directory=directory,
            format_selector="best",
            output_template="%(title)s.%(ext)s",
        ),
        queue,
    )


def test_the_worker_runs_in_a_real_spawned_process_with_no_display(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`ARC-002` end to end, and Phase 1's sixth exit criterion: a **real session, headless**.

    Not mocked (`docs/project/TESTING.md` §6) — a mocked subprocess cannot fail the way a real one
    does, and `spawn` re-importing the module is exactly the behaviour under test.

    **This test called its child headless for a long time while inheriting the desktop**
    (`P1EXIT-R1`). `mp.Process` passes `os.environ` down, so `DISPLAY` was set in the child every
    time it ran. The name was the only headless thing about it.

    The correction that preceded this one split the problem in half and fixed the wrong half: it
    added a scrubbed interpreter that only resolved yt-dlp, so the *condition* was real and the
    *workload* was somewhere else. A display dependency introduced anywhere after resolution —
    in `run_session`, in the queue, in the protocol — would have left both green.

    So the scrub happens here, around the process that runs the real session. `monkeypatch.delenv`
    removes the variables from this process before `spawn` copies the environment, and
    `_spawn_target` asserts their absence in the child that actually does the work.
    """

    for variable in DISPLAY_VARIABLES:
        monkeypatch.delenv(variable, raising=False)

    context = mp.get_context("spawn")
    queue: Any = context.Queue()
    process = context.Process(target=_spawn_target, args=(queue, str(tmp_path)))
    process.start()
    process.join(timeout=60)

    assert process.exitcode == 0, (
        f"the spawned worker exited {process.exitcode}. Two mutations produce this and the "
        f"child's traceback in captured stderr tells them apart: the display guard in "
        f"`_spawn_target` firing means this process failed to scrub `DISPLAY`, while a "
        f"`KeyError: 'DISPLAY'` from inside `run_session` means the worker path itself grew a "
        f"display dependency. Both are P1EXIT-R1 failures; only the second is a product defect."
    )

    messages = []
    while not queue.empty():
        messages.append(queue.get_nowait())

    validate_sequence(SessionKind.PROBE, messages)
    probed = next(m for m in messages if isinstance(m, Probed))
    assert probed.media.title == "Spawned"


# --- the gate reads what was chosen, not what was asked for (`T-061`) --------------------------


def test_a_merging_selector_that_resolved_to_one_format_is_not_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T-061`, the defect itself: `bestvideo+bestaudio/best` over a progressive file.

    The `/best` branch wins, yt-dlp merges nothing, and ffmpeg is not needed — but the gate read
    the selector and saw a `+`. Four of the five built-in presets carry one, so a user without
    ffmpeg had a single usable preset and the first one they would reach for told them the
    download was impossible.

    `requested_formats` is absent and `format_id` is set, which is yt-dlp saying *one format
    satisfied this*. That fact was produced by the same probe the gate already runs.
    """
    monkeypatch.setattr(
        worker_module,
        "find_ffmpeg",
        lambda **_: FfmpegReport(path=None, source="not found on PATH"),
    )
    monkeypatch.setattr(
        worker_module,
        "_extract",
        fake_extract(
            {
                "title": "Clip",
                "webpage_url": "https://e.com/x",
                "ext": "mp4",
                "format_id": "mp4",
            }
        ),
    )
    monkeypatch.setattr(worker_module, "_validated_target", lambda *a, **k: tmp_path / "Clip.mp4")
    queue: Queue[Any] = Queue()

    worker_module.run_session(
        SessionKind.DOWNLOAD,
        "job-1",
        request_for(tmp_path, format_selector="bestvideo+bestaudio/best"),
        queue,
    )

    failures = [message for message in drain(queue) if isinstance(message, Failed)]
    assert not failures, (
        f"a download needing no merge was refused for want of ffmpeg: "
        f"{[(f.kind.value, f.message) for f in failures]}"
    )


def test_an_unresolved_extraction_still_falls_back_to_the_selector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The blind case keeps the conservative answer (`T-061`).

    A playlist, or an extraction that stopped before format selection, leaves neither
    `requested_formats` nor `format_id`. Guessing "no merge" there would spend the user's
    bandwidth and fail at merge time, which is exactly what `REQ-024` exists to prevent — so the
    selector still decides where nothing else can.
    """
    monkeypatch.setattr(
        worker_module,
        "find_ffmpeg",
        lambda **_: FfmpegReport(
            path=None, source="not found on PATH", unavailable_features=("merging",)
        ),
    )
    monkeypatch.setattr(
        worker_module,
        "_extract",
        fake_extract({"title": "Playlist", "webpage_url": "https://e.com/p"}),
    )
    queue: Queue[Any] = Queue()

    worker_module.run_session(
        SessionKind.DOWNLOAD,
        "job-1",
        request_for(tmp_path, format_selector="bestvideo+bestaudio"),
        queue,
    )

    failed = next(m for m in drain(queue) if isinstance(m, Failed))
    assert failed.kind is ErrorKind.FFMPEG_MISSING


# --- T-046: output path collision policy -------------------------------------------------------


def reserve_in_child(target: str, results: Any) -> None:
    """Claim `target` from a separate process and report what was won.

    Module-level and takes only picklable arguments, because `spawn` re-imports this module in a
    fresh interpreter — the same constraint every worker entry point in this project has.
    """
    from tracks_and_trails.downloader.worker import reserve_output_path

    results.put(str(reserve_output_path(Path(target))))


def test_two_downloads_whose_names_sanitize_alike_get_distinct_paths(tmp_path: Path) -> None:
    """`T-046`'s first criterion, and the reason `DAT-002` filed this task.

    `sanitize_component` is a pure function of one string and cannot answer "does this collide?".
    Two different videos whose titles sanitize identically have always resolved to one path; with
    `T-078`'s pool of N they now do it concurrently rather than one job at a time.
    """
    target = safe_output_path(tmp_path, "Clip.mp4")

    first = worker_module.reserve_output_path(target)
    second = worker_module.reserve_output_path(target)

    assert first != second, "two jobs were handed the same path, so one would overwrite the other"
    assert first.name == "Clip.mp4"
    assert second.name == "Clip (2).mp4"
    assert first.exists() and second.exists(), "a reservation must actually hold the name"


def test_the_residual_collision_t045_pins_is_resolved_here(tmp_path: Path) -> None:
    """`DAT-002`'s closing promise: absolute uniqueness lands in `T-046`.

    `T-045` kept `sanitize_component` idempotent, which makes a defused reserved name a fixed
    point — so a video titled `CON` and one already titled the defused form sanitize to the same
    component, and `DAT-002` says so plainly rather than claiming otherwise. Both still have to
    reach distinct files, and this is the layer that can promise it.
    """
    defused = safe_output_path(tmp_path, "CON.mp4")
    again = safe_output_path(tmp_path, f"{defused.stem}.mp4")
    assert defused == again, "this test is vacuous unless the two really do sanitize alike"

    first = worker_module.reserve_output_path(defused)
    second = worker_module.reserve_output_path(again)

    assert first != second, (
        "the residual collision DAT-002 pins still puts two downloads on one path"
    )


def test_an_existing_file_is_never_taken(tmp_path: Path) -> None:
    """Third criterion. The file already there may be the user's only copy of something."""
    target = tmp_path / "Clip.mp4"
    target.write_bytes(b"the user's existing download")

    reserved = worker_module.reserve_output_path(target)

    assert reserved != target
    assert target.read_bytes() == b"the user's existing download", (
        "an existing file was overwritten by a reservation"
    )


def test_the_preview_shows_the_resolved_name_before_anything_is_written(
    tmp_path: Path,
) -> None:
    """Second criterion (`REQ-011`): resolution is *visible*, not applied silently afterwards.

    A preview that disagrees with the write is the failure `DAT-002` kept `sanitize_component`
    idempotent to prevent — the user is shown one filename and gets another.
    """
    info = {"title": "Clip", "webpage_url": "https://e.com/x", "ext": "mp4"}
    resolved = worker_module._import_ytdlp(ytdlp_candidates(None))
    request = request_for(tmp_path, format_selector="best")

    first = worker_module.preview_path(request, dict(info), resolved)
    assert first.name == "Clip.mp4"
    assert not first.exists(), "the preview created a file; it is supposed to change nothing"

    (tmp_path / "Clip.mp4").write_bytes(b"already here")
    second = worker_module.preview_path(request, dict(info), resolved)

    assert second.name == "Clip (2).mp4", (
        f"the preview still promises {second.name!r} over a file that already exists"
    )


def test_concurrent_processes_cannot_both_win_one_path(tmp_path: Path) -> None:
    """Fourth criterion, **asserted against real concurrency** rather than by inspection.

    `ARC-002` gives every job its own process, so the racing writers share no memory: a
    check-then-create would let all of them see nothing and all of them proceed. Eight spawned
    processes claim the same target at once; each must come away with a different name.

    `spawn` explicitly, not the platform default, because that is what the application uses and
    `fork` would inherit state this test is not about.
    """
    target = tmp_path / "Clip.mp4"
    context = mp.get_context("spawn")
    results: Any = context.Queue()

    children = [
        context.Process(target=reserve_in_child, args=(str(target), results)) for _ in range(8)
    ]
    for child in children:
        child.start()
    for child in children:
        child.join(timeout=60)

    won = sorted(results.get_nowait() for _ in range(8))
    assert len(set(won)) == 8, (
        f"{8 - len(set(won))} of eight processes were handed a name another had already won: {won}"
    )
    assert all(Path(name).exists() for name in won)


def test_a_reservation_the_download_never_filled_is_given_back(tmp_path: Path) -> None:
    """A failed attempt must not consume the name its retry wants.

    Without this, retrying a failed download three times walks it to `Clip (4).mp4` while
    `Clip.mp4` through `Clip (3).mp4` sit in the user's folder as empty files.
    """
    target = tmp_path / "Clip.mp4"
    reserved = worker_module.reserve_output_path(target)
    assert reserved.exists()

    worker_module.release_output_path(reserved)

    assert not reserved.exists(), "the reservation outlived the download that never filled it"
    assert worker_module.reserve_output_path(target) == target, (
        "the released name was not available again, so a retry would walk to the next number"
    )


def test_a_reservation_with_bytes_in_it_is_never_deleted(tmp_path: Path) -> None:
    """Release is for reservations, and a file with content is not one any more.

    Deleting it would be exactly the data loss this policy exists to prevent, so size is the
    test — not a flag the process that reserved it might have died holding.
    """
    reserved = worker_module.reserve_output_path(tmp_path / "Clip.mp4")
    reserved.write_bytes(b"a real download")

    worker_module.release_output_path(reserved)

    assert reserved.exists() and reserved.read_bytes() == b"a real download", (
        "release deleted a file that had a download in it"
    )


def test_a_download_that_fails_releases_its_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The release is wired into the session, not merely available to it.

    Driven through `run_session` rather than by calling the helper, because "the download path
    releases on failure" is a claim about that path (`docs/project/TESTING.md` §13).
    """
    target = tmp_path / "Clip.mp4"
    monkeypatch.setattr(worker_module, "_validated_target", lambda *a, **k: target)

    def extract_that_fails(*_a: Any, **kwargs: Any) -> dict[str, Any]:
        if kwargs.get("probe_only"):
            return {"title": "Clip", "ext": "mp4", "webpage_url": "https://e.com/x"}
        raise RuntimeError("the download failed after the path was reserved")

    monkeypatch.setattr(worker_module, "_extract", extract_that_fails)
    monkeypatch.setattr(worker_module, "_ffmpeg_gap", lambda *a, **k: None)

    queue: Queue[Any] = Queue()
    worker_module.run_session(
        SessionKind.DOWNLOAD, "job-1", request_for(tmp_path), queue, cancel=None
    )

    assert not target.exists(), (
        "a failed download left its zero-byte reservation in the user's download folder, so a "
        "retry would be handed Clip (2).mp4"
    )


# --- T046-R1: the file that survives conversion is the one that must be claimed -------------


def test_a_postprocessor_that_changes_the_extension_never_overwrites_an_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Critical finding, at the worker seam.

    `%(ext)s` renders `webm`, so the old code reserved `Clip.webm` — and the MP3 extractor then
    wrote `Clip.mp3` **over the user's existing `Clip.mp3`**, because `O_EXCL` never covered the
    name that survived conversion. `overwrites=True` was documented as safe on the strength of a
    reservation that was for a different file.
    """
    theirs = tmp_path / "Clip.mp3"
    theirs.write_bytes(b"the user's own recording")

    monkeypatch.setattr(
        worker_module, "find_ffmpeg", lambda **_: FfmpegReport(path=None, source="absent")
    )
    monkeypatch.setattr(
        worker_module,
        "_extract",
        fake_extract(
            {"title": "Clip", "webpage_url": "https://e.com/x", "ext": "webm", "format_id": "webm"},
            produces="Clip.mp3",
        ),
    )
    monkeypatch.setattr(worker_module, "_validated_target", lambda *a, **k: tmp_path / "Clip.webm")
    queue: Queue[Any] = Queue()

    worker_module.run_session(
        SessionKind.DOWNLOAD, "job-1", request_for(tmp_path, format_selector="best"), queue
    )

    succeeded = next(m for m in drain(queue) if isinstance(m, Succeeded))
    assert theirs.read_bytes() == b"the user's own recording", (
        "the download replaced a file the user already had — the reservation covered the "
        "pre-conversion name and the postprocessor wrote past it"
    )
    assert Path(succeeded.output_path) != theirs
    assert Path(succeeded.output_path).exists()
    assert Path(succeeded.output_path).suffix == ".mp3", (
        "the claimed name kept the template's extension rather than the one that was produced"
    )


def test_an_audio_request_previews_the_extension_it_will_actually_produce(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T046-R2`: the case that made the preview lie, now derived exactly.

    `%(ext)s` renders the *pre-conversion* container, so an MP3 request previewed `Clip.webm` and
    wrote `Clip.mp3`. `preferredcodec` names the output outright, so this one is derivable — and
    deriving it for the **preview** is right even though `T046-R1` established that deriving it for
    the **claim** is not.
    """
    info = {"title": "Clip", "webpage_url": "https://e.com/x", "ext": "webm", "format_id": "webm"}
    resolved = worker_module._import_ytdlp(ytdlp_candidates(None))
    request = request_for(
        tmp_path,
        format_selector="bestaudio",
        media_kind=MediaKind.AUDIO,
        audio_codec=AudioCodec.MP3,
    )
    preview = worker_module.preview_path(request, dict(info), resolved)

    assert preview.suffix == ".mp3", (
        f"preview promised {preview.name!r}; an MP3 request converts, and %(ext)s renders the "
        "container that arrives rather than the one that is kept"
    )
    assert not worker_module.preview_is_provisional(request), (
        "an audio request's container is named by preferredcodec and is not a guess"
    )

    # An audio request converts, so it needs ffmpeg — refusing it is `T-061`'s gate doing its job
    # and would leave nothing to compare the preview against.
    ffmpeg = tmp_path / "ffmpeg"
    ffmpeg.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(
        worker_module, "find_ffmpeg", lambda **_: FfmpegReport(path=ffmpeg, source="for the test")
    )
    monkeypatch.setattr(worker_module, "_extract", fake_extract(info, produces="Clip.mp3"))
    monkeypatch.setattr(worker_module, "_validated_target", lambda *a, **k: tmp_path / "Clip.webm")
    queue: Queue[Any] = Queue()

    worker_module.run_session(SessionKind.DOWNLOAD, "job-1", request, queue)

    succeeded = next(m for m in drain(queue) if isinstance(m, Succeeded))
    assert succeeded.output_path == str(preview), (
        f"preview promised {preview.name!r}, but the completed download was "
        f"{Path(succeeded.output_path).name!r}"
    )


def test_an_original_audio_request_is_labelled_rather_than_predicted(
    tmp_path: Path,
) -> None:
    """`ORIGINAL` carries yt-dlp's `best`, and its container is decided after the download.

    Substituting the codec name would render `Clip.best`, which is not a file anybody gets — and
    substituting the *source* container is what `T046-R4` disproved against a real download. So
    nothing is substituted and the preview is labelled.
    """
    info = {"title": "Clip", "webpage_url": "https://e.com/x", "ext": "webm", "format_id": "webm"}
    resolved = worker_module._import_ytdlp(ytdlp_candidates(None))
    request = request_for(
        tmp_path,
        format_selector="bestaudio",
        media_kind=MediaKind.AUDIO,
        audio_codec=AudioCodec.ORIGINAL,
    )

    preview = worker_module.preview_path(request, dict(info), resolved)

    assert preview.suffix == ".webm", (
        f"preview promised {preview.name!r}; nothing is substituted for ORIGINAL, because the "
        "container it lands in is not knowable before the write"
    )
    # *(This test's docstring used to say ORIGINAL "keeps the source container, so the rendered
    # extension was already right". `T046-R4` disproved that with a real download: AAC inside an
    # `.mp4` is copied into an `.m4a`. The rendered extension is not right — it is merely the best
    # available, which is why the case is labelled rather than promised.)*
    assert worker_module.preview_is_provisional(request), (
        "ORIGINAL was presented as exact; yt-dlp decides its container by running ffprobe on the "
        "downloaded file, which does not exist when the preview is drawn"
    )


def test_an_audio_request_is_exact_even_with_a_merging_selector(tmp_path: Path) -> None:
    """Extraction decides the container whatever the selector did, so it is not a guess.

    The selector may merge streams; `preferredcodec` then converts the result, so the output is
    named by the request either way. Without this the audio branch of `preview_is_provisional` is
    unreachable by any test — a mutation deleting it survived, because every other audio fixture
    uses a selector with no `+` in it and reaches the same answer by the other route.
    """
    merging_audio = request_for(
        tmp_path,
        format_selector="bestvideo+bestaudio",
        media_kind=MediaKind.AUDIO,
        audio_codec=AudioCodec.MP3,
    )

    assert not worker_module.preview_is_provisional(merging_audio), (
        "an MP3 request was called provisional because its selector merges; extraction converts "
        "whatever the merge produced, so preferredcodec still names the output"
    )


def test_a_merging_request_says_its_preview_is_provisional(tmp_path: Path) -> None:
    """The residual `REQ-011`'s amendment covers (2026-08-01, maintainer).

    When yt-dlp merges a separate video and audio stream it chooses the container by its own
    rules, which are not derivable from the request. `T-046` rejected predicting a name to reserve
    against; showing that same prediction as a promise is the identical mistake one field over. So
    the preview is **labelled** rather than quietly wrong.
    """
    info = {"title": "Clip", "webpage_url": "https://e.com/x", "ext": "webm", "format_id": "137"}
    resolved = worker_module._import_ytdlp(ytdlp_candidates(None))

    merging = request_for(tmp_path, format_selector="bestvideo+bestaudio")
    single = request_for(tmp_path, format_selector="best")

    assert worker_module.preview_is_provisional(merging), (
        "a merging selector's container is yt-dlp's to choose, so the preview cannot promise it"
    )
    assert not worker_module.preview_is_provisional(single), (
        "a single progressive format is written as downloaded; nothing can change its container"
    )
    # And the path is still shown either way — provisional means labelled, not withheld.
    assert worker_module.preview_path(merging, dict(info), resolved).name.startswith("Clip")


def test_mergeall_also_says_its_preview_is_provisional(tmp_path: Path) -> None:
    """yt-dlp has a merging selector that contains no ``+`` at all.

    ``mergeall`` is parsed by yt-dlp into one merged format assembled from every selected stream.
    Looking only for the binary ``+`` operator therefore labels this container as exact even
    though yt-dlp chooses it by the same rules as any other merge.
    """
    request = request_for(tmp_path, format_selector="mergeall")

    assert worker_module.preview_is_provisional(request), (
        "mergeall asks yt-dlp to merge streams but was presented as an exact output path"
    )


def test_two_downloads_converting_to_one_name_get_two_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The concurrent half of the same finding.

    Two jobs whose *post-processed* names collide are the case the reservation never saw: their
    pre-conversion names differ, so nothing contended, and both then wrote `Clip.mp3`. Run in
    sequence here because the claim is about the claim being atomic per name, which
    `reserve_output_path` already proves across processes for the pre-conversion case.
    """
    monkeypatch.setattr(
        worker_module, "find_ffmpeg", lambda **_: FfmpegReport(path=None, source="absent")
    )
    monkeypatch.setattr(worker_module, "_validated_target", lambda *a, **k: tmp_path / "Clip.webm")

    written: list[Path] = []
    for job_id in ("job-1", "job-2"):
        monkeypatch.setattr(
            worker_module,
            "_extract",
            fake_extract(
                {
                    "title": "Clip",
                    "webpage_url": "https://e.com/x",
                    "ext": "webm",
                    "format_id": "webm",
                },
                produces="Clip.mp3",
            ),
        )
        queue: Queue[Any] = Queue()
        worker_module.run_session(
            SessionKind.DOWNLOAD, job_id, request_for(tmp_path, format_selector="best"), queue
        )
        succeeded = next(m for m in drain(queue) if isinstance(m, Succeeded))
        written.append(Path(succeeded.output_path))

    assert written[0] != written[1], (
        f"both downloads claimed {written[0]}; the second replaced the first"
    )
    assert all(path.exists() for path in written)


def test_the_staging_directory_does_not_outlive_the_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A private directory in the user's downloads folder must not accumulate.

    Asserted on the folder rather than on the cleanup call, because what the user sees is the
    folder — and `_discard_staging` deliberately swallows its own failures.
    """
    monkeypatch.setattr(
        worker_module, "find_ffmpeg", lambda **_: FfmpegReport(path=None, source="absent")
    )
    monkeypatch.setattr(
        worker_module,
        "_extract",
        fake_extract(
            {"title": "Clip", "webpage_url": "https://e.com/x", "ext": "mp4", "format_id": "mp4"}
        ),
    )
    monkeypatch.setattr(worker_module, "_validated_target", lambda *a, **k: tmp_path / "Clip.mp4")
    queue: Queue[Any] = Queue()

    worker_module.run_session(
        SessionKind.DOWNLOAD, "job-1", request_for(tmp_path, format_selector="best"), queue
    )

    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(worker_module.STAGING_PREFIX)]
    assert leftovers == [], f"staging directories survived the download: {leftovers}"


def test_the_previewed_container_comes_from_yt_dlps_table_not_the_codec_name(
    tmp_path: Path,
) -> None:
    """`T046-R4`: the codec is **not** the extension, for three of the eight.

    yt-dlp copies `aac` and `alac` into **m4a** and `vorbis` into **ogg**. Using `codec.value`
    directly is right for mp3, opus, flac, wav and m4a and wrong for the rest — and being right
    most of the time is what makes a preview believed. Found by mutation: every existing preview
    test asked for MP3, where the two happen to agree.
    """
    expected = {
        AudioCodec.MP3: ".mp3",
        AudioCodec.AAC: ".m4a",
        AudioCodec.ALAC: ".m4a",
        AudioCodec.M4A: ".m4a",
        AudioCodec.VORBIS: ".ogg",
        AudioCodec.OPUS: ".opus",
        AudioCodec.FLAC: ".flac",
        AudioCodec.WAV: ".wav",
    }
    info = {"title": "Clip", "webpage_url": "https://e.com/x", "ext": "webm", "format_id": "webm"}
    resolved = worker_module._import_ytdlp(ytdlp_candidates(None))

    for codec, suffix in expected.items():
        request = request_for(
            tmp_path,
            format_selector="bestaudio",
            media_kind=MediaKind.AUDIO,
            audio_codec=codec,
        )
        preview = worker_module.preview_path(request, dict(info), resolved)
        assert preview.suffix == suffix, (
            f"{codec.value} previewed as {preview.suffix!r}; yt-dlp's ACODECS table says "
            f"{suffix!r}, and the codec name is not the container for aac, alac or vorbis"
        )
        assert not worker_module.preview_is_provisional(request), f"{codec.value} is derivable"


def test_original_stays_unpredictable_even_if_yt_dlp_names_a_container_for_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The `ORIGINAL` guard is a decision about *us*, not a gap in yt-dlp's table.

    `ACODECS` has no `best` key today, so the guard and the lookup currently give the same answer
    and a mutation removing it survived. It is kept rather than deleted because it encodes
    something the table cannot: even if yt-dlp named a container for `best`, that container is
    chosen by `ffprobe` on the downloaded file and by the *downloaded* extension, so it would still
    not be knowable when the preview is drawn.

    Simulated by giving the table a `best` entry, which is the only way to reach the guard.
    """
    from yt_dlp.postprocessor import ffmpeg as ffmpeg_pp

    monkeypatch.setitem(ffmpeg_pp.ACODECS, "best", ("mp4", None, []))

    request = request_for(
        tmp_path,
        format_selector="bestaudio",
        media_kind=MediaKind.AUDIO,
        audio_codec=AudioCodec.ORIGINAL,
    )

    assert worker_module.audio_extension_for(AudioCodec.ORIGINAL) is None, (
        "a container yt-dlp names for 'best' was taken as a prediction; it still depends on "
        "ffprobe of a file that does not exist when the preview is drawn"
    )
    assert worker_module.preview_is_provisional(request)


# --- T-113: the partial file's lifetime (REQ-017, UX-008) --------------------------------------
#
# `UX-008`'s table, one test per row that this layer owns. The kill row is
# `tests/integration/test_end_to_end.py`, because only a real `SIGKILL` can establish it.


def test_a_jobs_staging_directory_is_the_same_one_every_time_it_runs(tmp_path: Path) -> None:
    """**The whole of the resume mechanism** (`T-113`).

    yt-dlp continues from a `.part` it finds at the path it is told to write. The only thing that
    ever stopped this application resuming was `tempfile.mkdtemp` — unique per *call* — so the
    next attempt looked in a directory nothing had written to. Asserted as a property of the
    function rather than through a download, because it is a property of the function.
    """
    first = worker_module.staging_directory(tmp_path, "job-1")
    again = worker_module.staging_directory(tmp_path, "job-1")
    other = worker_module.staging_directory(tmp_path, "job-2")

    assert first == again, "two attempts at one job would look in two directories"
    assert first != other, "two jobs would share a directory and race for one name"
    assert first.parent == tmp_path, (
        "the staging directory left the output folder, so claiming the finished file stops being "
        "a rename within one filesystem (T046-R1)"
    )
    assert not first.exists(), "asking where a partial would be created a directory"


def test_a_failed_download_keeps_its_partial_for_the_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`UX-008`: kept on failure, because a retry after a network error is what resume is for.

    The old `finally` discarded whatever the outcome, which is right for a download that landed
    and throws away the head start in the one case `UX-002` retries automatically.
    """
    monkeypatch.setattr(
        worker_module, "find_ffmpeg", lambda **_: FfmpegReport(path=None, source="absent")
    )
    monkeypatch.setattr(worker_module, "_validated_target", lambda *a, **k: tmp_path / "Clip.mp4")

    def extract_then_fail(
        _adapter: Any,
        _request: Any,
        _resolved: Any,
        _reporter: Any,
        *,
        probe_only: bool,
        output_template: str | None = None,
        **_extra: Any,
    ) -> dict[str, Any]:
        info = {"title": "Clip", "webpage_url": "https://e.com/x", "ext": "mp4"}
        if probe_only:
            return info
        # A download that wrote some bytes and then failed — the shape a dropped connection has.
        asked = Path(output_template or "")
        asked.parent.mkdir(parents=True, exist_ok=True)
        asked.with_suffix(".mp4.part").write_bytes(b"half a download")
        raise OSError("the connection dropped")

    monkeypatch.setattr(worker_module, "_extract", extract_then_fail)
    queue: Queue[Any] = Queue()

    worker_module.run_session(
        SessionKind.DOWNLOAD, "job-1", request_for(tmp_path, format_selector="best"), queue
    )

    assert any(isinstance(message, Failed) for message in drain(queue))
    partial = worker_module.resumable_partial(tmp_path, "job-1")
    assert partial is not None and partial.read_bytes() == b"half a download", (
        "the failure threw its partial away, so the retry starts from zero"
    )


def test_a_cancelled_download_leaves_its_partial_for_the_parent_to_decide(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**`T113-R3`**: the worker does not end the partial's life, because it cannot.

    This branch used to delete it, which was wrong twice over. The worker cannot tell *why* it is
    stopping — a user's Cancel and an orderly shutdown reach it identically, and `T113-R2` says
    only one of them means the download is unwanted — and it is not reached at all when the parent
    escalates to `terminate()` or `kill()`, so an uncooperative worker kept its partial whatever
    the intent was. `DownloadManager` decides, after the process is gone; the manager suite is
    where that is asserted.
    """
    monkeypatch.setattr(
        worker_module, "find_ffmpeg", lambda **_: FfmpegReport(path=None, source="absent")
    )
    monkeypatch.setattr(worker_module, "_validated_target", lambda *a, **k: tmp_path / "Clip.mp4")

    def extract_then_cancel(
        _adapter: Any,
        _request: Any,
        _resolved: Any,
        _reporter: Any,
        *,
        probe_only: bool,
        output_template: str | None = None,
        **_extra: Any,
    ) -> dict[str, Any]:
        info = {"title": "Clip", "webpage_url": "https://e.com/x", "ext": "mp4"}
        if probe_only:
            return info
        asked = Path(output_template or "")
        asked.parent.mkdir(parents=True, exist_ok=True)
        asked.with_suffix(".mp4.part").write_bytes(b"half a download")
        raise worker_module.SessionCancelledError("the user cancelled this session")

    monkeypatch.setattr(worker_module, "_extract", extract_then_cancel)
    queue: Queue[Any] = Queue()

    worker_module.run_session(
        SessionKind.DOWNLOAD, "job-1", request_for(tmp_path, format_selector="best"), queue
    )

    outcome = next(m for m in drain(queue) if isinstance(m, Failed))
    assert outcome.kind is ErrorKind.CANCELLED
    partial = worker_module.resumable_partial(tmp_path, "job-1")
    assert partial is not None and partial.read_bytes() == b"half a download", (
        "the worker decided the partial's fate from a branch that cannot know the intent, and "
        "that the escalated stop paths never reach"
    )


def test_asking_about_a_partial_that_does_not_exist_is_not_an_error(tmp_path: Path) -> None:
    """Every caller asks about jobs that never ran — `remove` cannot know which have partials."""
    assert worker_module.resumable_partial(tmp_path, "never-ran") is None
    # Idempotent, and safe for a directory that was never created.
    worker_module.discard_staging_for(tmp_path, "never-ran")
    worker_module.discard_staging_for(tmp_path, "never-ran")


# --- T109-R3 / T109-R4: the media and its sidecars are one family ------------------------------


def _staged_with_subtitle(directory: Path, *languages: str) -> tuple[Path, dict[str, Any]]:
    """A staging directory holding a finished media file and one subtitle per language."""
    staging = directory / f"{worker_module.STAGING_PREFIX}-job-1"
    staging.mkdir(parents=True)
    (staging / "Clip.mp4").write_bytes(b"media")
    requested: dict[str, Any] = {}
    for language in languages:
        path = staging / f"Clip.{language}.vtt"
        path.write_text(f"{language} subtitles", encoding="utf-8")
        requested[language] = {"filepath": str(path)}
    return staging, {"requested_subtitles": requested}


def test_a_sidecar_collision_moves_the_whole_family(tmp_path: Path) -> None:
    """**`T109-R4`.** With `Clip.mp4` free and `Clip.de.vtt` taken, the subtitle used to land as
    `Clip.de (2).vtt` — no longer the conventional sidecar for `Clip.mp4`, so a player associates
    the *old* one and ignores what was just downloaded.

    Both must move together or neither: the index is chosen for the family.
    """
    staging, result = _staged_with_subtitle(tmp_path, "de")
    stale = tmp_path / "Clip.de.vtt"
    stale.write_text("an older subtitle", encoding="utf-8")

    written, kept = worker_module.claim_outputs(
        result,
        staging=staging,
        stem="Clip",
        target=tmp_path / "Clip.mp4",
        produced=staging / "Clip.mp4",
        writing_subtitles=True,
    )

    assert written.name == "Clip (2).mp4", (
        f"the media took the free name {written.name!r} and left its subtitle behind"
    )
    assert [path.name for path in kept] == ["Clip (2).de.vtt"]
    assert stale.read_text(encoding="utf-8") == "an older subtitle", "a pre-existing file was lost"


def test_a_family_keeps_one_basename_when_both_names_are_occupied(tmp_path: Path) -> None:
    """The other collision: media *and* subtitle taken. One index, chosen for both."""
    staging, result = _staged_with_subtitle(tmp_path, "de", "en")
    (tmp_path / "Clip.mp4").write_bytes(b"older media")
    (tmp_path / "Clip.de.vtt").write_text("older de", encoding="utf-8")

    written, kept = worker_module.claim_outputs(
        result,
        staging=staging,
        stem="Clip",
        target=tmp_path / "Clip.mp4",
        produced=staging / "Clip.mp4",
        writing_subtitles=True,
    )

    assert written.name == "Clip (2).mp4"
    assert sorted(path.name for path in kept) == ["Clip (2).de.vtt", "Clip (2).en.vtt"]
    assert all(path.name.startswith(written.stem) for path in kept), (
        "a member of the family took a different basename, which is what T109-R4 is"
    )


def test_an_uncollided_family_keeps_the_plain_name(tmp_path: Path) -> None:
    """The common case, asserted so the family logic cannot quietly number everything."""
    staging, result = _staged_with_subtitle(tmp_path, "de")

    written, kept = worker_module.claim_outputs(
        result,
        staging=staging,
        stem="Clip",
        target=tmp_path / "Clip.mp4",
        produced=staging / "Clip.mp4",
        writing_subtitles=True,
    )

    assert written.name == "Clip.mp4"
    assert [path.name for path in kept] == ["Clip.de.vtt"]
    assert kept[0].read_text(encoding="utf-8") == "de subtitles"


def test_a_requested_subtitle_that_never_arrived_fails_the_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**`T109-R3`**: the job must not report success having discarded an output.

    Driven through `run_session` rather than through `claim_outputs`, because the finding is about
    the *outcome*: the claim failure was logged, `_run` ignored it, the cleanup deleted the file,
    and `Succeeded` went back. The staging directory is asserted intact too — `T-113` keeps a
    failed attempt's work, so nothing the download produced is thrown away with the verdict.
    """
    monkeypatch.setattr(
        worker_module, "find_ffmpeg", lambda **_: FfmpegReport(path=None, source="absent")
    )
    monkeypatch.setattr(worker_module, "_validated_target", lambda *a, **k: tmp_path / "Clip.mp4")

    def extract(
        _adapter: Any,
        _request: Any,
        _resolved: Any,
        _reporter: Any,
        *,
        probe_only: bool,
        output_template: str | None = None,
        **_extra: Any,
    ) -> dict[str, Any]:
        info = {"title": "Clip", "webpage_url": "https://e.com/x", "ext": "mp4"}
        if probe_only:
            return info
        asked = Path(output_template or "")
        asked.parent.mkdir(parents=True, exist_ok=True)
        asked.write_bytes(b"media")
        # yt-dlp names a subtitle it was asked to write and does not produce the file.
        return {
            **info,
            "requested_downloads": [{"filepath": str(asked)}],
            "requested_subtitles": {"de": {"filepath": str(asked.with_suffix(".de.vtt"))}},
        }

    monkeypatch.setattr(worker_module, "_extract", extract)
    queue: Queue[Any] = Queue()

    worker_module.run_session(
        SessionKind.DOWNLOAD,
        "job-1",
        replace(
            request_for(tmp_path, format_selector="best"),
            subtitle_languages=("de",),
            embed_subtitles=False,
        ),
        queue,
    )

    messages = drain(queue)
    assert not any(isinstance(message, Succeeded) for message in messages), (
        "the job reported success without the subtitle file the user asked for"
    )
    failure = next(message for message in messages if isinstance(message, Failed))
    assert failure.kind is ErrorKind.DISK
    assert "Clip.de.vtt" in failure.message, failure.message
    assert worker_module.staging_directory(tmp_path, "job-1").is_dir(), (
        "the cleanup ran on a failed session and took the downloaded media with it"
    )


def test_an_embedded_subtitle_that_was_deleted_is_not_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The valid case the missing-file check must not swallow (`T109-R3`).

    `FFmpegEmbedSubtitle` runs with `already_have_subtitle` false, so yt-dlp deletes each file once
    it is inside the container — the entry survives in `requested_subtitles` with a `filepath` that
    no longer exists, and that absence *is* the embed having worked. Only the request can tell the
    two apart, which is why `writing_subtitles` is passed rather than inferred.

    ffmpeg is reported present because embedding needs it (`REQ-024`) — the gate refuses the
    request otherwise, and the session would fail for a reason that has nothing to do with this.
    """
    monkeypatch.setattr(
        worker_module,
        "find_ffmpeg",
        lambda **_: FfmpegReport(path=tmp_path / "ffmpeg", source="supplied for the test"),
    )
    monkeypatch.setattr(worker_module, "_validated_target", lambda *a, **k: tmp_path / "Clip.mp4")

    def extract(
        _adapter: Any,
        _request: Any,
        _resolved: Any,
        _reporter: Any,
        *,
        probe_only: bool,
        output_template: str | None = None,
        **_extra: Any,
    ) -> dict[str, Any]:
        info = {"title": "Clip", "webpage_url": "https://e.com/x", "ext": "mp4"}
        if probe_only:
            return info
        asked = Path(output_template or "")
        asked.parent.mkdir(parents=True, exist_ok=True)
        asked.write_bytes(b"media")
        return {
            **info,
            "requested_downloads": [{"filepath": str(asked)}],
            "requested_subtitles": {"de": {"filepath": str(asked.with_suffix(".de.vtt"))}},
        }

    monkeypatch.setattr(worker_module, "_extract", extract)
    queue: Queue[Any] = Queue()

    worker_module.run_session(
        SessionKind.DOWNLOAD,
        "job-1",
        replace(
            request_for(tmp_path, format_selector="best"),
            subtitle_languages=("de",),
            embed_subtitles=True,
        ),
        queue,
    )

    messages = drain(queue)
    failed = [m for m in messages if isinstance(m, Failed)]
    assert not failed, (
        f"an embedded subtitle's expected absence was reported as a failure: {failed}"
    )
    succeeded = next(m for m in messages if isinstance(m, Succeeded))
    assert Path(succeeded.output_path).name == "Clip.mp4"


def test_a_partially_claimed_multi_language_set_leaves_nothing_half_moved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A claim that fails partway must give every reservation back (`T109-R3`).

    Otherwise the family's failure leaves zero-byte files standing in for outputs that are still in
    staging — the shape `release_output_path` exists to prevent, one level up.
    """
    staging, result = _staged_with_subtitle(tmp_path, "de", "en")
    moved: list[Path] = []
    original = Path.replace

    def fail_on_the_second_move_out(self: Path, target: Any) -> Path:
        """Break the second move *out of staging*, and let the rollback's moves back work.

        Patching every `replace` would also break the recovery this test is about, and the test
        would then be asserting that a broken filesystem stays broken rather than that the code
        puts things back.
        """
        if self.parent == staging:
            if len(moved) >= 1:
                raise OSError("the disk went away")
            moved.append(Path(target))
        return original(self, target)

    monkeypatch.setattr(Path, "replace", fail_on_the_second_move_out)

    with pytest.raises(UnsafePathError):
        worker_module.claim_outputs(
            result,
            staging=staging,
            stem="Clip",
            target=tmp_path / "Clip.mp4",
            produced=staging / "Clip.mp4",
            writing_subtitles=True,
        )

    monkeypatch.undo()
    leftovers = sorted(path.name for path in tmp_path.iterdir() if path.is_file())
    assert leftovers == [], (
        f"reservations or half-moved outputs were left in the download folder: {leftovers}"
    )
    assert sorted(path.name for path in staging.iterdir()) == [
        "Clip.de.vtt",
        "Clip.en.vtt",
        "Clip.mp4",
    ], "the download's own work did not all end up back in staging for the retry"


# --- T109-R8: a reported source is contained before anything moves -----------------------------


def test_a_sidecar_reported_through_a_dotdot_spelling_is_refused(tmp_path: Path) -> None:
    """**`T109-R8`, Critical.** `staging in path.parents` compares *components*, not files.

    `staging/../Clip.de.vtt` has `staging` among its parents and names a file beside the directory
    rather than in it — so a user-owned file at that path was moved into the download's output
    family under a name they had not asked for. This is the reviewer's own probe: bytes the session
    did not create, at the adjacent path, reported through the `..` spelling.
    """
    staging, _ = _staged_with_subtitle(tmp_path, "de")
    victim = tmp_path / "Clip.de.vtt"
    victim.write_bytes(b"the user's own subtitle")
    reported = {"requested_subtitles": {"de": {"filepath": str(staging / ".." / "Clip.de.vtt")}}}

    with pytest.raises(UnsafePathError, match="outside its own working directory"):
        worker_module.claim_outputs(
            reported,
            staging=staging,
            stem="Clip",
            target=tmp_path / "Clip.mp4",
            produced=staging / "Clip.mp4",
            writing_subtitles=True,
        )

    assert victim.read_bytes() == b"the user's own subtitle", (
        "a file the session never created was moved into its output family"
    )
    assert sorted(path.name for path in tmp_path.iterdir() if path.is_file()) == ["Clip.de.vtt"], (
        "the refusal left reservations behind, so it happened after the family was taken"
    )


def test_a_sidecar_that_is_a_symlink_out_of_staging_is_refused(
    tmp_path: Path, symlinks: SymlinkCapability
) -> None:
    """The spelling a purely textual check cannot see at all.

    `is_contained` resolves, so the question asked is *where does this file live*, not *what does
    its path look like* — `T034-R1` is the same lesson at the destination end of this module.
    """
    staging, _ = _staged_with_subtitle(tmp_path, "de")
    (staging / "Clip.de.vtt").unlink()
    outside = tmp_path / "important.txt"
    outside.write_bytes(b"not ours")
    symlinks.create(staging / "Clip.de.vtt", outside)
    reported = {"requested_subtitles": {"de": {"filepath": str(staging / "Clip.de.vtt")}}}

    with pytest.raises(UnsafePathError, match="outside its own working directory"):
        worker_module.claim_outputs(
            reported,
            staging=staging,
            stem="Clip",
            target=tmp_path / "Clip.mp4",
            produced=staging / "Clip.mp4",
            writing_subtitles=True,
        )

    assert outside.read_bytes() == b"not ours"


def test_a_media_source_outside_staging_is_refused(tmp_path: Path) -> None:
    """The `produced` path had **no** containment check at all — the same class, unguarded.

    It comes out of `requested_downloads[].filepath`, which is yt-dlp's report rather than this
    application's instruction, so it is an input like any other.
    """
    staging, _ = _staged_with_subtitle(tmp_path)
    elsewhere = tmp_path / "somebody-elses.mp4"
    elsewhere.write_bytes(b"not ours either")

    with pytest.raises(UnsafePathError, match="outside its own working directory"):
        worker_module.claim_outputs(
            {},
            staging=staging,
            stem="Clip",
            target=tmp_path / "Clip.mp4",
            produced=elsewhere,
            writing_subtitles=False,
        )

    assert elsewhere.read_bytes() == b"not ours either"


def test_the_staging_directory_itself_is_not_a_source(tmp_path: Path) -> None:
    """`is_contained` answers `True` for the directory itself, and a directory is not an output."""
    staging, _ = _staged_with_subtitle(tmp_path)

    with pytest.raises(UnsafePathError, match="outside its own working directory"):
        worker_module.claim_outputs(
            {},
            staging=staging,
            stem="Clip",
            target=tmp_path / "Clip.mp4",
            produced=staging,
            writing_subtitles=False,
        )


# --- T113-R1: a crafted job id cannot reach outside the output directory -----------------------
#
# `Job.id` is validated as non-empty text and nothing more. It comes off a database row, which a
# user can edit and a corrupt write can mangle, and `staging_directory` joins it into a path that
# `_run` creates with `parents=True` and `discard_staging_for` removes with `shutil.rmtree`.


CRAFTED_IDS = [
    "../../../../outside",
    "../outside",
    "..\\..\\outside",
    "/etc",
    "C:\\Windows",
    "....//....//outside",
    "..",
]


@pytest.mark.parametrize("job_id", CRAFTED_IDS)
def test_a_crafted_job_id_names_a_directory_inside_the_output_folder(
    tmp_path: Path, job_id: str
) -> None:
    """The join itself, before anything is created or removed.

    Asserted through `staging_directory` rather than through `derived_component`, because the
    defect was in the *composition*: the helper can be perfect and the call site still concatenate.
    """
    downloads = tmp_path / "downloads" / "nested"
    downloads.mkdir(parents=True)

    staging = worker_module.staging_directory(downloads, job_id)

    assert is_contained(staging, downloads), f"{job_id!r} named {staging}"
    assert staging.parent == downloads
    assert staging.name.startswith(worker_module.STAGING_PREFIX)


@pytest.mark.parametrize("job_id", CRAFTED_IDS)
def test_a_crafted_job_id_cannot_create_or_delete_outside_the_output_folder(
    tmp_path: Path, job_id: str
) -> None:
    """**`T113-R1`, Critical — the reviewer's own probe.**

    A sentinel outside the chosen directory, then the exact sequence the worker and the manager
    perform: `mkdir(parents=True)` on the computed staging path, then `discard_staging_for`. With
    the id spelled into the name, `../../../../outside` resolved to a real directory and the
    sentinel was deleted.
    """
    downloads = tmp_path / "downloads" / "nested"
    downloads.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "user-file.txt"
    sentinel.write_bytes(b"the user's own file")

    staging = worker_module.staging_directory(downloads, job_id)
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "Clip.mp4.part").write_bytes(b"half a download")
    worker_module.discard_staging_for(downloads, job_id)

    assert sentinel.read_bytes() == b"the user's own file", (
        f"the id {job_id!r} reached outside the output directory and deleted a user's file"
    )
    assert outside.is_dir(), f"the id {job_id!r} removed a directory outside the output folder"
    assert not staging.exists(), "the job's own directory was not cleaned up"


def test_a_discard_refuses_a_staging_path_outside_its_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The belt-and-braces check at the `rmtree`, driven by making the derivation lie.

    `derived_component` makes an escaping name unrepresentable, so this branch is unreachable
    through the id — which is exactly what was said about `safe_output_path`'s final containment
    check until `T034-R1` reached it through a symlink. A recursive delete is the one operation
    here where being wrong is unrecoverable, so it asks rather than assumes.
    """
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "user-file.txt").write_bytes(b"the user's own file")
    monkeypatch.setattr(worker_module, "staging_directory", lambda *_: outside)

    worker_module.discard_staging_for(downloads, "job-1")

    assert (outside / "user-file.txt").exists(), "the rmtree ran on a path outside the directory"


def test_a_symlink_at_the_staging_name_fails_the_session_before_anything_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, symlinks: SymlinkCapability
) -> None:
    """**`T113-R1`, Critical.** A digest makes the *name* safe and says nothing about what is at it.

    `mkdir(parents=True, exist_ok=True)` accepts a symlink to a directory without complaint —
    a symlink to a directory *is* a directory to every question `mkdir` asks — and the download
    then writes through it. A reviewer created `outside/Clip.mp4` that way, at a path the delete
    guard correctly refuses to `rmtree` and cannot un-write.

    Driven through `run_session`, which is the entry point that does the `mkdir`. The previous
    tests proved `derived_component` and `staging_directory`, and the write happens one layer down
    from both — the same gap that let a mutation survive on the first correction.
    """
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_bytes(b"the user's own file")
    symlinks.create(
        worker_module.staging_directory(downloads, "job-1"), outside, target_is_directory=True
    )

    monkeypatch.setattr(
        worker_module, "find_ffmpeg", lambda **_: FfmpegReport(path=None, source="absent")
    )
    monkeypatch.setattr(
        worker_module,
        "_extract",
        fake_extract({"title": "Clip", "webpage_url": "https://e.com/x", "ext": "mp4"}),
    )
    monkeypatch.setattr(worker_module, "_validated_target", lambda *a, **k: downloads / "Clip.mp4")
    queue: Queue[Any] = Queue()

    worker_module.run_session(
        SessionKind.DOWNLOAD, "job-1", request_for(downloads, format_selector="best"), queue
    )

    messages = drain(queue)
    assert not any(isinstance(message, Succeeded) for message in messages), (
        "the session reported success having written through a symlink out of the download folder"
    )
    failure = next(message for message in messages if isinstance(message, Failed))
    assert failure.kind is ErrorKind.DISK, failure
    assert sorted(path.name for path in outside.iterdir()) == ["sentinel.txt"], (
        "the download wrote outside the folder the user chose"
    )
    assert sentinel.read_bytes() == b"the user's own file"


def test_a_plain_file_at_the_staging_name_fails_rather_than_being_replaced(tmp_path: Path) -> None:
    """The other squatter. Refused rather than repaired: deleting what is there would be this
    application removing something it did not create, at a path it cannot explain."""
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    squatter = worker_module.staging_directory(downloads, "job-1")
    squatter.write_bytes(b"not a directory")

    with pytest.raises(UnsafePathError, match="not this download's own working directory"):
        worker_module.open_staging(downloads, "job-1")

    assert squatter.read_bytes() == b"not a directory"


def test_an_existing_staging_directory_is_reused_with_its_partial_intact(tmp_path: Path) -> None:
    """**The audit `T113-R1` asked for**: the new check must not discard what it protects.

    The directory is stable precisely so a killed attempt's `.part` is where the next one writes
    (`REQ-017`). A guard that cleared it to be safe would delete the head start the whole feature
    exists to keep, and would pass every negative test above while doing it.
    """
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    staging = worker_module.staging_directory(downloads, "job-1")
    staging.mkdir()
    (staging / "Clip.mp4.part").write_bytes(b"half a download")

    reused = worker_module.open_staging(downloads, "job-1")

    assert reused == staging
    assert (reused / "Clip.mp4.part").read_bytes() == b"half a download"
    assert worker_module.resumable_partial(downloads, "job-1") is not None


def test_a_symlinked_staging_name_reports_no_partial_to_resume_from(
    tmp_path: Path, symlinks: SymlinkCapability
) -> None:
    """Reporting what is inside a foreign directory as *this job's partial* answers for a file the
    session never wrote — and it is the manager that reads this, to decide what to clean up."""
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "Clip.mp4.part").write_bytes(b"somebody else's partial")
    symlinks.create(
        worker_module.staging_directory(downloads, "job-1"), outside, target_is_directory=True
    )

    assert worker_module.resumable_partial(downloads, "job-1") is None
    worker_module.discard_staging_for(downloads, "job-1")
    assert (outside / "Clip.mp4.part").exists(), "the cleanup followed the link out of the folder"


def test_a_symlink_pointing_somewhere_else_inside_the_download_folder_is_refused(
    tmp_path: Path, symlinks: SymlinkCapability
) -> None:
    """Containment alone is not enough, and a mutation is what said so.

    Removing the `is_symlink` half left every outside case still refused — `is_contained` resolves,
    so a link *out* of the folder is caught by containment on its own. A link to another directory
    **inside** the folder is not: the download would write into a directory of the user's that this
    session did not create, and `claim_outputs` would leave whatever it did not move behind. It is
    also `T-046`'s collision, reached sideways — two jobs pointed at one directory.
    """
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    theirs = downloads / "Music I Already Had"
    theirs.mkdir()
    (theirs / "track.mp3").write_bytes(b"the user's own music")
    symlinks.create(
        worker_module.staging_directory(downloads, "job-1"), theirs, target_is_directory=True
    )

    with pytest.raises(UnsafePathError, match="not this download's own working directory"):
        worker_module.open_staging(downloads, "job-1")

    assert sorted(path.name for path in theirs.iterdir()) == ["track.mp3"]


def test_a_symlink_planted_during_the_mkdir_is_still_caught(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, symlinks: SymlinkCapability
) -> None:
    """Why the check runs **after** the create as well as before it.

    Checking first and creating afterwards leaves a window: the check passes on a path that does
    not exist, and a symlink planted before the `mkdir` is then accepted by it. A mutation dropping
    the second check survived every other test here, because every other test plants the link
    before the call — this one plants it *inside* the `mkdir`, which is the only way to observe the
    ordering deterministically.
    """
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "sentinel.txt").write_bytes(b"the user's own file")
    staging = worker_module.staging_directory(downloads, "job-1")
    original = Path.mkdir

    def plant_then_create(self: Path, *args: Any, **kwargs: Any) -> None:
        if self == staging:
            symlinks.create(staging, outside, target_is_directory=True)
            return
        original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", plant_then_create)

    with pytest.raises(UnsafePathError, match="stopped being"):
        worker_module.open_staging(downloads, "job-1")

    monkeypatch.undo()
    assert sorted(path.name for path in outside.iterdir()) == ["sentinel.txt"]


# --- T282-R2: the application's level has to reach a real worker -------------------------------

#: A parent that configures logging at a level, spawns a **real** worker through
#: `prepare_this_worker` — the documented contract for being one — and prints what reached the
#: application log.
#:
#: **A file rather than `python -c`**, because `spawn` re-imports the parent's `__main__` in the
#: child and there is nothing to import from a `-c` string.
WORKER_LEVEL_PROBE = """
import logging, multiprocessing, sys
from pathlib import Path

from tracks_and_trails.core.logging import (
    configure_logging,
    stop_listening_for_worker_logs,
    worker_log_level,
    worker_log_queue,
)
from tracks_and_trails.downloader import worker as worker_module


def be_a_worker(queue, level):
    worker_module.prepare_this_worker(queue, "job-under-test", level)
    logging.getLogger("tracksandtrails.worker").debug("MARKER-DEBUG")
    logging.getLogger("tracksandtrails.worker").info("MARKER-INFO")


if __name__ == "__main__":
    chosen = getattr(logging, sys.argv[1])
    path = configure_logging(directory=Path(sys.argv[2]), level=chosen)
    queue = worker_log_queue()
    child = multiprocessing.get_context("spawn").Process(
        target=be_a_worker, args=(queue, worker_log_level())
    )
    child.start()
    child.join(60)
    stop_listening_for_worker_logs()
    print(path.read_text(encoding="utf-8"))
"""


@pytest.mark.parametrize(
    ("level", "debug_expected"),
    [
        pytest.param("DEBUG", True, id="DEBUG reaches the application log"),
        pytest.param("INFO", False, id="and is absent at the default level"),
    ],
)
def test_the_applications_level_reaches_a_real_worker(
    tmp_path: Path, level: str, debug_expected: bool
) -> None:
    """`T282-R2`: `--log-level=DEBUG` must capture worker records, not only the GUI's.

    **The level stopped at the parent.** `run()` handed it to `configure_logging` and nothing
    carried it further, so `worker_logging_handler` fell back to `INFO` and a child's `DEBUG`
    records were dropped **before the queue** — meaning the flag could not capture the one class of
    record it is most wanted for, including the session-header failure at `worker.py`.

    **A real spawned worker, through `prepare_this_worker`**, because that is the contract every
    production worker goes through and the discard happened inside it. An in-process call would
    exercise the handler and not the path.

    **Both directions**, though the `INFO` arm proves less than it looks and the difference is
    worth stating: at `INFO` the parent's own handlers drop a worker `DEBUG` record regardless, so
    carrying `DEBUG` into every worker unconditionally produces an identical log here and this test
    cannot see it. `test_the_level_offered_to_a_worker_is_the_one_this_process_uses` is what
    notices — the volume on the queue, not the content of the file.
    """
    script = tmp_path / "worker_level_probe.py"
    script.write_text(WORKER_LEVEL_PROBE, encoding="utf-8")
    logs = tmp_path / "logs"

    finished = subprocess.run(
        [sys.executable, str(script), level, str(logs)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert finished.returncode == 0, f"the probe failed: {finished.stderr}"
    written = finished.stdout
    assert "MARKER-INFO" in written, (
        f"no worker record reached the application log at {level}, so this proves nothing about "
        f"the DEBUG one: {written!r}"
    )
    assert ("MARKER-DEBUG" in written) is debug_expected, (
        f"at {level} the worker's DEBUG record should {'' if debug_expected else 'not '}reach the "
        f"application log: {written!r}"
    )
