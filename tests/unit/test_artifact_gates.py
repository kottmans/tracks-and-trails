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
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

import pytest

from tests.capabilities import SymlinkCapability

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


def bindings(root: Path, names: Sequence[str] = ("Core", "Gui", "Widgets")) -> None:
    """The PySide6 extension modules — the files the loader half is asked about."""
    directory = root / "_internal" / "PySide6"
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / f"Qt{name}.abi3.so").write_bytes(b"\x7fELF")


def resolves(module: str, target: Path) -> str:
    """One `ldd` line, in the shape the real one emits."""
    return f"\tlibQt6{module}.so.6 => {target} (0x00007f0000000000)\n"


def install_ldd(
    monkeypatch: pytest.MonkeyPatch,
    directory: Path,
    *,
    per_binding: dict[str, str] | None = None,
    default: str = "",
    returncode: int = 0,
) -> None:
    """Put an `ldd` on `PATH` that prints canned output, keyed by the binding it is asked about.

    **A script, not a patched `subprocess.run`.** The call the gate actually makes — building the
    argument list, reading the exit status, decoding the output — then stays inside the test. The
    real `ldd` is no use here: these trees hold files *shaped* like libraries, not libraries.
    """
    canned = directory / "canned"
    canned.mkdir(parents=True)
    (canned / "_default").write_text(default, encoding="utf-8")
    for name, text in (per_binding or {}).items():
        (canned / name).write_text(text, encoding="utf-8")

    script = directory / "ldd"
    script.write_text(
        "#!/bin/sh\n"
        'name=$(basename "$1")\n'
        f'if [ -f "{canned}/$name" ]; then cat "{canned}/$name"; '
        f'else cat "{canned}/_default"; fi\n'
        f"exit {returncode}\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")


@pytest.fixture
def linked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A complete artifact whose bindings resolve every required Qt module inside it."""
    root = build(tmp_path / "app")
    bindings(root)
    internal = root / "_internal"
    install_ldd(
        monkeypatch,
        tmp_path / "bin",
        default="".join(
            resolves(module, internal / f"libQt6{module}.so.6")
            for module in gates.REQUIRED_QT_MODULES
        ),
    )
    return root


def test_a_complete_artifact_passes_every_check(linked: Path) -> None:
    """The positive control. Without it, every case below passes a check that always fails."""
    for _name, check in gates.CHECKS:
        assert check(linked) == []


def test_a_missing_qt_module_fails(linked: Path) -> None:
    """§8 item 11 · `LIC-001` — the one failure here that is a licence breach, not a defect."""
    for library in (linked / "_internal").glob("libQt6Widgets.so*"):
        library.unlink()
    problems = gates.qt_ships_as_shared_libraries(linked)
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


# --- §8 item 11, the three ways it was wrong (`T323-R1`) -------------------------------------


def test_a_dangling_symlink_is_not_a_usable_library(
    linked: Path, symlinks: SymlinkCapability
) -> None:
    """`T323-R1`'s counterexample, reproduced.

    The bundle carries Qt at two paths and the second is a **symlink, not an independent copy**,
    so deleting the real file left a link that `rglob` still returned and the glob still counted.
    The mutation that exposed it — delete `libQt6Widgets.so.6` — had been reported as caught.
    """
    internal = linked / "_internal"
    mirrored = internal / "PySide6" / "Qt" / "lib"
    mirrored.mkdir(parents=True)
    symlinks.create(mirrored / "libQt6Widgets.so.6", internal / "libQt6Widgets.so.6")
    assert gates.qt_ships_as_shared_libraries(linked) == [], "both copies present should pass"

    (internal / "libQt6Widgets.so.6").unlink()
    problems = gates.qt_ships_as_shared_libraries(linked)
    assert any("QtWidgets" in problem and "dangling" in problem for problem in problems), problems


def test_every_binding_is_inspected_not_only_the_first_few(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T323-R1`'s second defect: the loader half inspected `extensions[:4]`.

    QtWidgets sorts **fifth** in a real build, so the one module the mutation removed was the one
    the check never asked about. The cap is gone; this pins that it stays gone.
    """
    modules = ("Core", "Gui", "Network", "Qml", "Widgets")
    root = build(tmp_path / "app")
    bindings(root, modules)
    internal = root / "_internal"
    assert sorted(root.rglob("PySide6/Qt*.abi3.so"))[4].name == "QtWidgets.abi3.so"

    per_binding = {
        f"Qt{module}.abi3.so": resolves(module, internal / f"libQt6{module}.so.6")
        for module in modules
    }
    install_ldd(monkeypatch, tmp_path / "bin", per_binding=per_binding)
    assert gates._qt_links_resolve_inside_the_artifact(root) == []

    # Only the fifth binding's evidence is withdrawn, which a four-binding cap could not see.
    per_binding["QtWidgets.abi3.so"] = ""
    install_ldd(monkeypatch, tmp_path / "later", per_binding=per_binding)
    problems = gates._qt_links_resolve_inside_the_artifact(root)
    assert problems and "libQt6Widgets" in problems[0], problems


def test_an_inspection_that_cannot_run_is_not_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T323-R1`'s third defect: no `ldd` returned *no problems*, which is indistinguishable
    from *no problem found*."""
    root = build(tmp_path / "app")
    bindings(root)
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    problems = gates._qt_links_resolve_inside_the_artifact(root)
    assert problems and "ldd" in problems[0], problems


def test_a_loader_that_fails_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same rule one step in: a non-zero exit is a failed inspection, not a clean one."""
    root = build(tmp_path / "app")
    bindings(root)
    install_ldd(monkeypatch, tmp_path / "bin", default="not a dynamic executable\n", returncode=1)
    problems = gates._qt_links_resolve_inside_the_artifact(root)
    assert any("ldd failed on" in problem for problem in problems), problems


def test_a_build_that_borrows_the_host_qt_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Presence cannot see this: the libraries are all there, and nothing links to them.

    `T323-R1` observed a mutated build resolving to the system copy and reporting incompatible
    private Qt symbols, so this is the failure mode that actually happened.
    """
    root = build(tmp_path / "app")
    bindings(root)
    install_ldd(
        monkeypatch,
        tmp_path / "bin",
        default="".join(
            resolves(module, Path("/lib64") / f"libQt6{module}.so.6")
            for module in gates.REQUIRED_QT_MODULES
        ),
    )
    problems = gates._qt_links_resolve_inside_the_artifact(root)
    assert problems and "outside the artifact" in problems[0], problems


def test_a_dependency_the_loader_cannot_find_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = build(tmp_path / "app")
    bindings(root)
    install_ldd(monkeypatch, tmp_path / "bin", default="\tlibQt6Widgets.so.6 => not found\n")
    problems = gates._qt_links_resolve_inside_the_artifact(root)
    assert any("cannot find it" in problem for problem in problems), problems


def test_bindings_that_declare_no_qt_at_all_do_not_pass_silently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The positive-evidence requirement, which is what a static build would look like.

    Without it a binding declaring no Qt dependency produces no problems and no evidence, and the
    check reports a pass having established nothing.
    """
    root = build(tmp_path / "app")
    bindings(root)
    install_ldd(monkeypatch, tmp_path / "bin", default="\tlibc.so.6 => /lib64/libc.so.6\n")
    problems = gates._qt_links_resolve_inside_the_artifact(root)
    assert len(problems) == len(gates.REQUIRED_QT_MODULES), problems
    assert all("nothing establishes" in problem for problem in problems), problems


def test_windows_keeps_the_presence_check_alone(tmp_path: Path) -> None:
    """`dumpbin` is not on a stock Windows machine, so item 11 there is presence only.

    That is a **narrower guarantee stated rather than implied** — this pins the disposition so a
    later reader does not mistake the Windows pass for a linkage pass.
    """
    root = build(tmp_path / "app")
    directory = root / "_internal" / "PySide6"
    directory.mkdir(parents=True)
    (directory / "QtCore.pyd").write_bytes(b"MZ")
    assert gates._qt_links_resolve_inside_the_artifact(root) == []


# --- §8 item 13, what escaped the scan (`T323-R2`) -------------------------------------------


@pytest.mark.parametrize(
    ("name", "why"),
    [
        ("noextension", "an extensionless file, which the suffix allowlist never opened"),
        ("planted.bin", "a suffix the allowlist did not list"),
        ("data.dat", "another one"),
        ("ordinary.txt", "the case the allowlist did cover, kept as the control"),
    ],
)
def test_a_planted_cookie_is_found_whatever_the_file_is_called(
    tmp_path: Path, name: str, why: str
) -> None:
    """`T323-R2`: the scan ran patterns only over an allowlist of text suffixes.

    Nothing is decided by suffix now. A file is opened, read and scanned whatever it is called.
    """
    root = build(tmp_path / "app")
    (root / "_internal" / name).write_text("Cookie: sid=abc123; other=def\n", encoding="utf-8")
    problems = gates.no_secrets_or_personal_paths(root)
    assert problems and "cookie header carrying a value" in problems[0], f"{why}: {problems}"


def test_a_cookie_header_inside_a_real_binary_is_found(tmp_path: Path) -> None:
    """A NUL byte decides which half of the vocabulary runs, **not** whether the file is scanned.

    The first fix for `T323-R2` skipped NUL-bearing files outright, which caught the reviewer's
    `.bin` only because it happened to have no NUL in its first block. This is the harder case.
    """
    root = build(tmp_path / "app")
    planted = b"\x7fELF" + bytes(64) + b"Cookie: sid=abc123\n" + bytes(64)
    (root / "_internal" / "libsomething.so.1").write_bytes(planted)
    problems = gates.no_secrets_or_personal_paths(root)
    assert problems and "cookie header carrying a value" in problems[0], problems


def test_a_long_line_is_still_scanned(tmp_path: Path) -> None:
    """`T323-R2`: lines past column 2000 were skipped, so a leak on one survived."""
    root = build(tmp_path / "app")
    padding = "x" * 5000
    (root / "_internal" / "bundle.js").write_text(
        f"{padding} Cookie: sid=abc123 {padding}", encoding="utf-8"
    )
    problems = gates.no_secrets_or_personal_paths(root)
    assert problems and "cookie header carrying a value" in problems[0], problems


def test_a_cookie_store_is_a_leak_by_its_name(tmp_path: Path) -> None:
    """**Filenames count as much as contents**, and the earlier version only looked at bytes.

    An empty `cookies.txt` is the case that makes the point: nothing inside it matches anything.
    """
    root = build(tmp_path / "app")
    (root / "_internal" / "cookies.txt").write_text("", encoding="utf-8")
    problems = gates.no_secrets_or_personal_paths(root)
    assert problems and "named as a cookie store" in problems[0], problems


def test_credentials_inside_a_url_are_found(tmp_path: Path) -> None:
    root = build(tmp_path / "app")
    (root / "_internal" / "endpoint.cfg").write_text(
        "url = https://builder:hunter2@internal.invalid/api\n", encoding="utf-8"
    )
    problems = gates.no_secrets_or_personal_paths(root)
    assert problems and "credentials inside a URL" in problems[0], problems


def test_a_package_specifier_is_not_credentials(tmp_path: Path) -> None:
    """**The false positive that decided the pattern**, kept as a case.

    `core/logging`'s `_BARE_USERINFO` is for userinfo with *no* scheme — a full URL is `_URL`'s
    job there. Pointed at an artifact it matched `npm:meriyah@6.1.4` in yt-dlp's bundled solver,
    measured. So this medium gets its own pattern, which requires a scheme and `user:pass@`.
    """
    root = build(tmp_path / "app")
    (root / "_internal" / "solver.py").write_text(
        'REGISTRY = ["npm:meriyah@6.1.4", "npm:acorn@8.11.3", "pypi:urllib3@2.2.1"]\n',
        encoding="utf-8",
    )
    assert gates.no_secrets_or_personal_paths(root) == []


def test_a_cookie_format_string_is_not_a_leak(tmp_path: Path) -> None:
    """**The other false positive that was real**: `Received cookie: {lenstr}` in `libkrb5.so.3`.

    The redactor is right to match that — in a *log line* it is about to be filled in with a real
    cookie. In a shipped artifact a format string is not a leak, so the value has to look like
    `name=value`.
    """
    root = build(tmp_path / "app")
    (root / "_internal" / "messages.txt").write_text(
        "Received cookie: {lenstr}\nSet-Cookie: %s\ncookie: \n", encoding="utf-8"
    )
    assert gates.no_secrets_or_personal_paths(root) == []


def test_the_cheap_half_is_not_bounded_by_the_byte_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bound applies to `COSTLY_PATTERNS` only, so it cannot become a gap for the rest.

    Measured cost is the reason for the split: `_COOKIE_FILENAME` takes 171s on `libQt6Gui.so.6`
    and truncating to the cap does not help, while the two cheap patterns cover the artifact's
    whole 206 MB of binaries in 24s.
    """
    monkeypatch.setattr(gates, "MAX_SCANNED_BYTES", 16)
    root = build(tmp_path / "app")
    (root / "_internal" / "big.txt").write_text(
        ("filler " * 200) + "Cookie: sid=abc123\n", encoding="utf-8"
    )
    problems = gates.no_secrets_or_personal_paths(root)
    assert any("cookie header carrying a value" in problem for problem in problems), problems


def test_truncating_the_costly_half_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**Reported, never silent** (`T323-R2`). A bound nobody can see is a gap nobody can see."""
    monkeypatch.setattr(gates, "MAX_SCANNED_BYTES", 16)
    root = build(tmp_path / "app")
    (root / "_internal" / "big.txt").write_text("harmless " * 200, encoding="utf-8")
    problems = gates.no_secrets_or_personal_paths(root)
    assert any("stopped early" in problem and "big.txt" in problem for problem in problems), (
        problems
    )


#: Why this machine cannot seal a file against its owner, or `""` when it can.
#:
#: **Branched on `sys.platform`, which is what mypy narrows.** The first version called
#: `os.geteuid()` unguarded — fine on Linux, where the attribute exists, and a hard error on the
#: Windows job: *"Module has no attribute geteuid"*. Local `mypy` could not see it because local
#: `mypy` runs with Linux stubs; `mypy --platform win32` does, and that is the check this needed.
#:
#: Windows is skipped for a second reason worth stating rather than folding in: `chmod(0o000)`
#: does not deny the owner a read there at all, so the test would not be measuring a sealed file.
if sys.platform == "win32":
    CANNOT_SEAL_A_FILE = "Windows does not deny the owner a mode-000 read"
elif os.geteuid() == 0:
    CANNOT_SEAL_A_FILE = "root can read a mode-000 file"
else:
    CANNOT_SEAL_A_FILE = ""


@pytest.mark.skipif(bool(CANNOT_SEAL_A_FILE), reason=CANNOT_SEAL_A_FILE or "the file can be sealed")
def test_an_unreadable_file_is_not_a_clean_file(tmp_path: Path) -> None:
    """`T323-R1`'s lesson, one check over: an inspection that cannot run is not a pass."""
    root = build(tmp_path / "app")
    sealed = root / "_internal" / "sealed.dat"
    sealed.write_text("anything", encoding="utf-8")
    sealed.chmod(0o000)
    try:
        problems = gates.no_secrets_or_personal_paths(root)
        assert problems and "could not be read" in problems[0], problems
    finally:
        sealed.chmod(0o644)


def test_the_install_prefix_is_provenance_in_a_file_that_quotes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T323-R3`: a file may legitimately quote where the interpreter was installed.

    A `sysconfig` dump is the obvious case. So the *one string* is stripped and the question is
    asked again — and a home path that is not that string is still a finding in the same file.
    """
    home = (tmp_path / "home" / "builder").resolve()
    prefix = home / "hostedtoolcache" / "Python" / "3.14.7" / "x64"
    prefix.mkdir(parents=True)
    monkeypatch.setattr(gates.Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(gates.sys, "base_prefix", str(prefix))

    root = build(tmp_path / "app")
    dump = root / "_internal" / "sysconfig_data.json"
    dump.write_text(f'{{"prefix": "{prefix}"}}', encoding="utf-8")
    assert gates.no_secrets_or_personal_paths(root) == []

    dump.write_text(
        f'{{"prefix": "{prefix}", "src": "{home}/checkouts/private"}}', encoding="utf-8"
    )
    problems = gates.no_secrets_or_personal_paths(root)
    assert problems and "home directory" in problems[0], problems


def test_the_bundled_interpreters_own_build_paths_are_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`T323-R4`: the first fix for this did not work, and CI is where that showed.

    `frozen linux` failed on **110** hits across `libpython3.14.so.1.0` and `lib-dynload/*.so`,
    for *both* the home literal and the user-name-in-a-path literal. Exempting `sys.base_prefix`
    could not cover them, because **that is not the path in the binary**: CPython embeds the
    directory it was *built* in, and whoever built it did so somewhere. Here the install prefix is
    deliberately nowhere near home, which is the configuration the exemption has to survive.
    """
    home = (tmp_path / "home" / "runner").resolve()
    home.mkdir(parents=True)
    monkeypatch.setattr(gates.Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(gates.sys, "base_prefix", "/opt/hostedtoolcache/Python/3.14.7/x64")
    monkeypatch.setattr(gates.getpass, "getuser", lambda: "runner")

    root = build(tmp_path / "app")
    internal = root / "_internal"
    dynload = internal / "python3.14" / "lib-dynload"
    dynload.mkdir(parents=True)
    embedded = f"{home}/work/python/cpython/Modules/\x00/runner/lib".encode()
    (internal / "libpython3.14.so.1.0").write_bytes(b"\x7fELF" + embedded)
    (dynload / "_bz2.cpython-314-x86_64-linux-gnu.so").write_bytes(b"\x7fELF" + embedded)

    assert gates.no_secrets_or_personal_paths(root) == []


def test_the_interpreter_exemption_does_not_cover_anything_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**The half that keeps it an exemption rather than a hole.**

    The same bytes in a file the interpreter does not own are still a finding — which is what
    would catch a release built in the maintainer's own checkout.
    """
    home = (tmp_path / "home" / "runner").resolve()
    home.mkdir(parents=True)
    monkeypatch.setattr(gates.Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(gates.sys, "base_prefix", "/opt/hostedtoolcache/Python/3.14.7/x64")

    root = build(tmp_path / "app")
    (root / "_internal" / "build_settings.json").write_text(
        f'{{"checkout": "{home}/software_projects/tracks-and-trails"}}', encoding="utf-8"
    )
    problems = gates.no_secrets_or_personal_paths(root)
    assert problems and "home directory" in problems[0], problems


def test_only_path_literals_are_excused_in_an_interpreter_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Provenance explains a build path. It does not explain a cookie.

    So the exemption is scoped to the two path literals, and everything else in the vocabulary
    still runs over the interpreter's files.
    """
    home = (tmp_path / "home" / "runner").resolve()
    home.mkdir(parents=True)
    monkeypatch.setattr(gates.Path, "home", classmethod(lambda cls: home))

    root = build(tmp_path / "app")
    runtime = root / "_internal" / "libpython3.14.so.1.0"
    runtime.write_bytes(f"\x7fELF{home}/work\x00Cookie: sid=abc123\n".encode())
    problems = gates.no_secrets_or_personal_paths(root)
    assert problems and "cookie header carrying a value" in problems[0], problems


def test_a_netrc_reference_is_not_excused_by_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`.netrc` sits outside the exemption, and that claim was in a docstring untested.

    A mutation that excused *every* literal in an interpreter file — not only the two path ones —
    survived the whole file. Where CPython was built explains a build path. It does not explain a
    reference to a credentials store, so that one is still reported wherever it appears.
    """
    home = (tmp_path / "home" / "runner").resolve()
    home.mkdir(parents=True)
    monkeypatch.setattr(gates.Path, "home", classmethod(lambda cls: home))

    root = build(tmp_path / "app")
    runtime = root / "_internal" / "libpython3.14.so.1.0"
    runtime.write_bytes(f"\x7fELF{home}/work\x00/root/.netrc\x00".encode())
    problems = gates.no_secrets_or_personal_paths(root)
    assert problems and "netrc" in problems[0], problems


@pytest.mark.parametrize(
    ("relative", "owned"),
    [
        ("_internal/libpython3.14.so.1.0", True),
        ("_internal/python3.14/lib-dynload/_bz2.cpython-314-x86_64-linux-gnu.so", True),
        ("_internal/python3.dll", True),
        ("_internal/DLLs/_socket.pyd", True),
        # Everything this project or its dependencies put there is **not** exempt.
        ("_internal/build_settings.json", False),
        ("_internal/yt_dlp/extractor/youtube.py", False),
        ("_internal/tracks_and_trails/app.pyc", False),
        ("_internal/libQt6Core.so.6", False),
        ("tracks-and-trails", False),
    ],
)
def test_interpreter_ownership_is_narrow(relative: str, owned: bool) -> None:
    """*"Anything under `_internal`"* would be the whole bundle, including this application's own
    code and yt-dlp's — which is the difference between an exemption and a hole."""
    assert gates.is_interpreter_owned(Path(relative)) is owned
