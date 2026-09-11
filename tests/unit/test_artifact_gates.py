"""The four release-gate checks, over trees built to fail them (`T-323`).

**Each check here is asked to fail before it is trusted to pass** — `T031-R2`'s rule. The checks
were also mutated against a **real** PyInstaller build, and the run ids are in `T-323`; these cases
are the portable half, so a change to the logic is caught without a five-minute build.

**One of them found a defect in itself this way.** `qt_ships_as_shared_libraries` originally only
globbed for the library files, and passed with `libQt6Widgets.so.6` deleted — the bundle carries Qt
twice, at `_internal/` and `_internal/PySide6/Qt/lib/`, so removing one copy left the other. The
check now also asks the loader where each dependency resolves.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

REPOSITORY = Path(__file__).resolve().parents[2]
TOOL = REPOSITORY / "packaging" / "artifact_gates.py"


def load() -> ModuleType:
    """By path, as `test_job_duration_report.py` loads its own: `packaging/` is not a
    package."""
    specification = importlib.util.spec_from_file_location("artifact_gates", TOOL)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


gates = load()


def build(root: Path, *, qt: bool = True, licences: bool = True, ytdlp: bool = True) -> Path:
    """A tree shaped like a one-dir build, with each property switchable off."""
    internal = root / "_internal"
    internal.mkdir(parents=True)
    if qt:
        for module in gates.REQUIRED_QT_MODULES:
            (internal / f"libQt6{module}.so.6").write_bytes(b"\x7fELF")
    if licences:
        directory = internal / "licenses"
        directory.mkdir()
        for name in gates.REQUIRED_LICENCES:
            (directory / name).write_text("licence text", encoding="utf-8")
    if ytdlp:
        (internal / "yt_dlp").mkdir()
        (internal / "yt_dlp" / "__init__.py").write_text("", encoding="utf-8")
    return root


def test_a_complete_artifact_passes_every_check(tmp_path: Path) -> None:
    """The positive control. Without it, every case below passes a check that always fails."""
    root = build(tmp_path / "app")
    for _name, check in gates.CHECKS:
        assert check(root) == []


def test_a_missing_qt_module_fails(tmp_path: Path) -> None:
    """§8 item 11 · `LIC-001` — the one failure here that is a licence breach, not a defect."""
    root = build(tmp_path / "app")
    for library in (root / "_internal").glob("libQt6Widgets.so*"):
        library.unlink()
    problems = gates.qt_ships_as_shared_libraries(root)
    assert problems and "QtWidgets" in problems[0]


def test_a_missing_licence_file_fails(tmp_path: Path) -> None:
    """§8 item 12. Each file, not just the directory — the directory existing proves nothing."""
    for name in gates.REQUIRED_LICENCES:
        root = build(tmp_path / name, licences=True)
        next(root.rglob("licenses")).joinpath(name).unlink()
        assert gates.licence_texts_are_present(root), f"deleting {name} was not caught"


def test_no_licences_directory_at_all_fails(tmp_path: Path) -> None:
    root = build(tmp_path / "app", licences=False)
    assert gates.licence_texts_are_present(root)


def test_the_licences_are_found_wherever_the_builder_put_them(tmp_path: Path) -> None:
    """PyInstaller puts `datas` under `_internal/`, not beside the executable.

    The first version looked only at the artifact root and reported the licences missing from a
    build that carried them — measured on a real build, not imagined.
    """
    root = build(tmp_path / "app")
    assert (root / "_internal" / "licenses").is_dir()
    assert gates.licence_texts_are_present(root) == []


def test_ffmpeg_needs_its_licence_only_where_it_is_bundled(tmp_path: Path) -> None:
    """`OPS-001` bundles ffmpeg on Windows alone, so a Linux artifact is not failed for
    lacking its licence."""
    without = build(tmp_path / "linux")
    assert gates.licence_texts_are_present(without) == []

    with_ffmpeg = build(tmp_path / "windows")
    (with_ffmpeg / "_internal" / "ffmpeg.exe").write_bytes(b"MZ")
    problems = gates.licence_texts_are_present(with_ffmpeg)
    assert problems and gates.FFMPEG_LICENCE in problems[0]

    next(with_ffmpeg.rglob("licenses")).joinpath(gates.FFMPEG_LICENCE).write_text("t")
    assert gates.licence_texts_are_present(with_ffmpeg) == []


def test_a_compiled_extension_in_ytdlp_fails(tmp_path: Path) -> None:
    """§8 item 9 · `OPS-002` — the wheel-extraction update needs the tree to stay pure Python."""
    for suffix in (".so", ".pyd"):
        root = build(tmp_path / f"app{suffix}")
        (root / "_internal" / "yt_dlp" / f"_speedups{suffix}").write_bytes(b"\x00")
        assert gates.ytdlp_is_pure_python(root), f"a{suffix} extension was not caught"


def test_a_missing_ytdlp_tree_fails_rather_than_passing_over_nothing(tmp_path: Path) -> None:
    """The vacuity guard: *"no compiled extensions"* is trivially true of no yt-dlp at all."""
    root = build(tmp_path / "app", ytdlp=False)
    assert gates.ytdlp_is_pure_python(root)


def test_a_personal_path_in_a_data_file_fails(tmp_path: Path) -> None:
    """§8 item 13 · `NFR-007` — nothing about the machine that built it."""
    root = build(tmp_path / "app")
    (root / "_internal" / "config.json").write_text(f'{{"cache": "{Path.home()}/.cache"}}')
    problems = gates.no_secrets_or_personal_paths(root)
    assert problems and "home directory" in problems[0]


def test_a_cookie_store_path_fails_through_the_shared_vocabulary(tmp_path: Path) -> None:
    """The patterns come from `core/logging`, so a class added there is scanned for here.

    This is `T015-R1`'s rule applied to a gate: one vocabulary, not two, because the second one is
    the one nobody updates.
    """
    root = build(tmp_path / "app")
    (root / "_internal" / "notes.txt").write_text("saved to /var/tmp/cookies.txt\n")
    problems = gates.no_secrets_or_personal_paths(root)
    assert problems and "cookie" in problems[0]


def test_an_ordinary_artifact_is_not_flagged(tmp_path: Path) -> None:
    """**The false positive that was real**, kept as a case.

    Searching for the bare user name reported `libbrotlicommon.so.1` — brotli's built-in English
    dictionary, which contains those four letters inside ordinary words, while the real home path
    appeared in no file at all. A gate that cries wolf on every build is one that gets switched
    off, so the name counts only bracketed by path separators.
    """
    root = build(tmp_path / "app")
    import getpass

    prose = f"research and reasoning about {getpass.getuser()}sonal matters"
    (root / "_internal" / "dictionary.txt").write_text(prose, encoding="utf-8")
    assert gates.no_secrets_or_personal_paths(root) == []
