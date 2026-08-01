"""The spawned worker (`T-012`).

`ai/TESTING.md` §6: **the process boundary is never mocked here.** A real child process is
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
from pathlib import Path
from queue import Queue
from typing import Any

import pytest

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
    however wrong both were (`ai/TESTING.md` §13). It takes the preview, then runs a real
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
    observe is not reported (`ai/TESTING.md` §13).
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
    all — which is exactly how `T012-R4` survived (`ai/TESTING.md` §13).
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


def test_a_symlink_out_of_the_directory_is_still_refused(tmp_path: Path, symlinks: None) -> None:
    """`T-034`'s own guarantee, kept as a direct check because no template can express it."""
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    target = tmp_path / "Downloads"
    target.mkdir()
    (target / "link").symlink_to(outside)

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

    Not mocked (`ai/TESTING.md` §6) — a mocked subprocess cannot fail the way a real one does,
    and `spawn` re-importing the module is exactly the behaviour under test.

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


# --- the resolved format reaches the parent (T-050, REQ-020) --------------------------------


def test_a_successful_download_reports_the_resolved_format_not_the_selector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T-050`: `format_used` is what yt-dlp settled on, never what the request asked for.

    The two are deliberately different strings here, because that is the only shape of this test
    that can fail for the right reason. Asserting `format_used == "137+140"` while the selector
    also happened to be `"137+140"` would pass against an implementation that stored the request's
    selector — which is the exact defect the task names: *the selector wearing that name*.
    """
    info = {
        "title": "Clip",
        "webpage_url": "https://e.com/x",
        "ext": "mp4",
        # What yt-dlp resolved the selector to.
        "format_id": "137+140",
    }
    messages = _run_download(
        tmp_path, monkeypatch, info, format_selector="bestvideo+bestaudio/best"
    )

    succeeded = next(m for m in messages if isinstance(m, Succeeded))
    assert succeeded.format_used == "137+140"
    assert succeeded.format_used != "bestvideo+bestaudio/best", (
        "the request's selector reached the field reserved for what was actually used"
    )


def test_a_download_that_resolves_no_format_reports_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No `format_id` means no honest answer, and `None` is how that is said.

    The alternative implementations both lie: `str(None)` stores the literal `"None"`, and falling
    back to the selector stores an intention as an outcome.
    """
    info = {"title": "Clip", "webpage_url": "https://e.com/x", "ext": "mp4"}
    messages = _run_download(tmp_path, monkeypatch, info, format_selector="best")

    succeeded = next(m for m in messages if isinstance(m, Succeeded))
    assert succeeded.format_used is None


def test_a_blank_resolved_format_is_reported_as_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty `format_id` is absence, not knowledge — and `Succeeded` would reject `""`.

    Without the normalising helper this raises out of the worker instead of reporting a success,
    turning a completed download into a protocol error.
    """
    info = {"title": "Clip", "webpage_url": "https://e.com/x", "ext": "mp4", "format_id": ""}
    messages = _run_download(tmp_path, monkeypatch, info, format_selector="best")

    succeeded = next(m for m in messages if isinstance(m, Succeeded))
    assert succeeded.format_used is None


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
    releases on failure" is a claim about that path (`ai/TESTING.md` §13).
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


def test_an_original_audio_request_previews_the_container_it_arrives_in(
    tmp_path: Path,
) -> None:
    """`ORIGINAL` carries yt-dlp's `best`, which means **keep the source codec** — not convert.

    Substituting an extension for it would render `Clip.best`, which is not a file anybody gets.
    Found by mutation: removing the `ORIGINAL` guard survived, because every other preview test
    either asks for MP3 or is not an audio request at all.
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
        f"preview promised {preview.name!r}; ORIGINAL keeps the source container, so the rendered "
        "extension was already right and nothing should have been substituted"
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
