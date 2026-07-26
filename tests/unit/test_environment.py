"""yt-dlp and ffmpeg resolution (`T-035`).

Two things are under test, and the second is the one that erodes quietly.

**Behavior**: the `OPS-002` resolution order, and an ffmpeg report that names what stops
working (`REQ-024`).

**The ownership boundary**: this module *locates*, `worker.py` *imports*. `ARCHITECTURE.md` §6
permits `import yt_dlp` in two modules and this is not one of them, so `environment.py` cannot
report a version or a usability verdict — both need the import. That boundary is asserted here
rather than left to the layering test alone, because the tempting way to erode it is to add a
helpful `version()` that reaches for `importlib`, which the layering test's `ast` analysis would
not necessarily see as an `import yt_dlp`.
"""

import ast
from pathlib import Path

import pytest

from tracks_and_trails.downloader import environment
from tracks_and_trails.downloader.environment import (
    FFMPEG_DEPENDENT_FEATURES,
    FfmpegReport,
    describe_candidates,
    find_ffmpeg,
    user_ytdlp_directory,
    ytdlp_candidates,
)

# --- resolution order (OPS-002, ARCHITECTURE.md §6) -----------------------------------------


def test_with_no_user_copy_the_baseline_is_the_only_present_candidate(tmp_path: Path) -> None:
    """`OPS-002`'s default: a fresh install runs the pinned baseline."""
    candidates = ytdlp_candidates(tmp_path / "absent")
    present = [c for c in candidates if c.exists]
    assert len(present) == 1
    assert present[0].path is None
    assert "baseline" in present[0].source


def test_a_user_copy_is_ordered_ahead_of_the_baseline(tmp_path: Path) -> None:
    """The whole point of `OPS-002`: a user fixes a broken site without waiting for a release."""
    user_copy = tmp_path / "ytdlp"
    user_copy.mkdir()
    candidates = ytdlp_candidates(user_copy)

    assert candidates[0].path == user_copy
    assert candidates[0].exists
    assert candidates[1].path is None
    assert [c.exists for c in candidates] == [True, True]


@pytest.mark.parametrize("layout", ["empty", "no yt_dlp package", "unexpected wheel layout"])
def test_a_user_directory_is_listed_even_when_it_looks_unusable(
    tmp_path: Path, layout: str
) -> None:
    """An acceptance criterion, and the one most likely to be "helpfully" broken later.

    Deciding a candidate is unusable requires importing it, which is `worker.py`'s job. A
    `yt_dlp/`-directory check here would be this module forming the verdict it may not form —
    and would be wrong for any wheel layout this code has not anticipated.
    """
    user_copy = tmp_path / "ytdlp"
    user_copy.mkdir()
    if layout == "no yt_dlp package":
        (user_copy / "something_else").mkdir()
    elif layout == "unexpected wheel layout":
        (user_copy / "yt_dlp-2026.7.4.dist-info").mkdir()

    assert ytdlp_candidates(user_copy)[0].exists


def test_a_file_where_the_user_directory_should_be_is_not_present(tmp_path: Path) -> None:
    """`is_dir()`, not `exists()`: a stray file cannot be prepended to `sys.path` usefully."""
    stray = tmp_path / "ytdlp"
    stray.write_text("not a directory", encoding="utf-8")
    assert not ytdlp_candidates(stray)[0].exists


def test_the_default_user_directory_is_not_doubled() -> None:
    """platformdirs inserts an author segment on Windows without `appauthor=False`.

    That produces `tracksandtrails/tracksandtrails/ytdlp`, matching none of `ARCHITECTURE.md`
    §5's paths — invisible on Linux, wrong on Windows. The trap `T-007` already hit once.
    """
    path = user_ytdlp_directory()
    assert path.name == "ytdlp"
    assert path.parent.name == environment.APP_SLUG
    assert path.parent.parent.name != environment.APP_SLUG


# --- the ownership boundary (ARCHITECTURE.md §6) ---------------------------------------------


def test_the_module_exposes_no_version_and_no_usability_verdict() -> None:
    """An acceptance criterion: the split must not erode back into this module by accident.

    Both a version and a "does it work" answer require importing yt-dlp, which §6 permits only
    in `worker.py` and `ytdlp_adapter.py`. A future helper named `version()` here would be a
    layering violation wearing a friendly name.
    """
    exported = {name for name in vars(environment) if not name.startswith("_")}
    forbidden = {"version", "ytdlp_version", "resolved_version", "verify", "validate", "is_usable"}
    assert not exported & forbidden, f"{exported & forbidden} belongs to worker.py, not here"

    candidate = ytdlp_candidates()[0]
    assert not hasattr(candidate, "version")
    assert not hasattr(candidate, "usable")


def imported_roots(module: object) -> set[str]:
    """Top-level package names this module actually imports, by parsing it.

    Parsed rather than substring-matched: the module's docstring discusses `yt_dlp` at length
    precisely to explain why it does not import it, and a naive `"yt_dlp" not in source` check
    fails on the explanation. That was the first version of this test.
    """
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))  # type: ignore[attr-defined]
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_the_module_never_imports_yt_dlp() -> None:
    """An acceptance criterion. `ARCHITECTURE.md` §6 permits the import in two modules only."""
    assert "yt_dlp" not in imported_roots(environment)


def test_the_module_cannot_reach_yt_dlp_dynamically() -> None:
    """Stronger than the layering test's static analysis, and the reason this test exists.

    `test_layering.py` looks for an `import yt_dlp` statement. `importlib.import_module("yt_dlp")`
    is not one, so it would pass that guard while violating §6 exactly as much. Blocking the
    tool rather than the spelling is what makes the boundary hold.
    """
    assert "importlib" not in imported_roots(environment)
    source = Path(environment.__file__).read_text(encoding="utf-8")
    assert "__import__" not in source


def test_the_module_imports_no_qt() -> None:
    """Resolution runs in the worker, which must stay Qt-free (`ARC-002`)."""
    roots = imported_roots(environment)
    assert "PySide6" not in roots
    assert "shiboken6" not in roots


# --- ffmpeg detection (REQ-024, OPS-001) -----------------------------------------------------


def test_ffmpeg_found_on_path_reports_available(tmp_path: Path) -> None:
    fake = tmp_path / "ffmpeg"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    fake.chmod(0o755)

    report = find_ffmpeg(search_path=str(tmp_path))
    assert report.available
    assert report.path == fake
    assert report.unavailable_features == ()


def test_ffmpeg_absent_names_every_feature_that_stops_working(tmp_path: Path) -> None:
    """`REQ-024`: report *which* features are unavailable, not merely that some are.

    A user told "some features are unavailable" cannot decide whether they care.
    """
    report = find_ffmpeg(search_path=str(tmp_path / "empty"))
    assert not report.available
    assert report.unavailable_features == FFMPEG_DEPENDENT_FEATURES
    assert "merging" in report.summary()
    assert "audio" in report.summary()


def test_an_explicit_override_is_honoured_first(tmp_path: Path) -> None:
    """`OPS-001` allows an override on both platforms."""
    override = tmp_path / "custom-ffmpeg"
    override.write_text("#!/bin/sh\n", encoding="utf-8")
    on_path = tmp_path / "onpath"
    on_path.mkdir()
    (on_path / "ffmpeg").write_text("#!/bin/sh\n", encoding="utf-8")
    (on_path / "ffmpeg").chmod(0o755)

    report = find_ffmpeg(override=override, search_path=str(on_path))
    assert report.path == override
    assert "override" in report.source


def test_a_missing_override_is_reported_not_silently_ignored(tmp_path: Path) -> None:
    """Falling back to `PATH` would mean the user's explicit setting had no effect, silently.

    `ARCHITECTURE.md` §6's rule for yt-dlp — never silently ignore an override — is the same
    principle, and a user who set a path deserves to be told it was wrong.
    """
    on_path = tmp_path / "onpath"
    on_path.mkdir()
    (on_path / "ffmpeg").write_text("#!/bin/sh\n", encoding="utf-8")
    (on_path / "ffmpeg").chmod(0o755)

    report = find_ffmpeg(override=tmp_path / "nope", search_path=str(on_path))
    assert not report.available
    assert "override" in report.source


def test_a_directory_named_ffmpeg_is_not_mistaken_for_the_binary(tmp_path: Path) -> None:
    override = tmp_path / "ffmpeg"
    override.mkdir()
    assert not find_ffmpeg(override=override).available


def test_detection_executes_nothing(tmp_path: Path) -> None:
    """`ARCHITECTURE.md` §9: no shell, and detection has no reason to run the binary either.

    Asserted against the source, because a subprocess call added later would still pass every
    behavioural test above.
    """
    source = Path(environment.__file__).read_text(encoding="utf-8")
    for forbidden in ("subprocess", "os.system", "shell=True", "popen"):
        assert forbidden not in source.lower(), f"{forbidden} in a detection-only module"


# --- privacy (NFR-007) ------------------------------------------------------------------------


def test_the_candidate_description_leaks_no_user_path(tmp_path: Path) -> None:
    """`NFR-007`. The user directory sits under the user's home, so logging it leaks a
    username into a file that may be attached to a bug report.

    The source label carries the useful fact — which candidate was chosen — without the path.
    """
    user_copy = tmp_path / "seans-secret-home" / "ytdlp"
    user_copy.mkdir(parents=True)

    description = describe_candidates(ytdlp_candidates(user_copy))
    assert "seans-secret-home" not in description
    assert str(user_copy) not in description
    assert "user-managed" in description and "present" in description


def test_the_ffmpeg_summary_leaks_no_override_path(tmp_path: Path) -> None:
    """The only path in play when ffmpeg is missing is one the user typed (`NFR-007`)."""
    override = tmp_path / "home" / "sean" / "ffmpeg-custom"
    report = find_ffmpeg(override=override)
    assert str(override) not in report.summary()
    assert "sean" not in report.summary()


def test_reports_are_immutable_and_carry_tuples() -> None:
    """These cross the process boundary to the worker (`ARC-002`), like every other value."""
    report = FfmpegReport(path=None, source="x", unavailable_features=FFMPEG_DEPENDENT_FEATURES)
    with pytest.raises(AttributeError):
        report.path = Path("/elsewhere")  # type: ignore[misc]
    assert isinstance(report.unavailable_features, tuple)

    candidate = ytdlp_candidates()[0]
    with pytest.raises(AttributeError):
        candidate.exists = False  # type: ignore[misc]
