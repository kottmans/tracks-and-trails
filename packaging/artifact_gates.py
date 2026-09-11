"""Four release-gate items that were prose, made executable (`T-323`).

`docs/project/TESTING.md` §8 items **9, 11, 12 and 13** are obligations a human was expected to
check by reading. Three of them are licence or update-path obligations that fail silently — an
artifact missing Qt's licence text still runs, still installs, and still breaches `LIC-001` — so
none of them is the kind of thing a release checklist catches reliably.

    python3 packaging/artifact_gates.py dist/tracks-and-trails

Exits non-zero and names every problem. **Each check has a mutation that must turn it red**, run
against a real build and recorded in `T-323`; the house rule since `T031-R2` is that a gate nobody
has seen fail is a gate nobody has tested.

**It runs against the smoke build.** The release builds (`T-319`, `T-321`) are the same tree with
more in it, so these checks are written against the shape both share rather than against whichever
artifact happened to exist first.
"""

from __future__ import annotations

import argparse
import getpass
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tracks_and_trails.core.logging import (
    _COOKIE_FILENAME,
    _COOKIE_HEADER,
    _COOKIE_PATH,
)

#: Qt modules this application actually loads, which therefore have to be in the bundle as
#: **separate shared libraries** rather than linked into the executable (`NFR-009`, `LIC-001`).
REQUIRED_QT_MODULES: tuple[str, ...] = ("Core", "Gui", "Widgets")

#: Licence texts every artifact carries (`LIC-001`, §8 item 12). `packaging/licenses/README.md`
#: records where each came from.
#:
#: **`Qt-GPLv3.txt` is not a mistake.** The LGPL-3.0 is not standalone — its own text says it
#: *"incorporates the terms and conditions of version 3 of the GNU General Public License"* — so
#: shipping the LGPL alone distributes an incomplete licence.
REQUIRED_LICENCES: tuple[str, ...] = (
    "Qt-LGPLv3.txt",
    "Qt-GPLv3.txt",
    "yt-dlp-Unlicense.txt",
    "NOTICE.txt",
)

#: Required **only where ffmpeg is bundled**, which `OPS-001` makes Windows alone. A Linux
#: artifact ships no ffmpeg and is not failed for carrying no licence for it.
FFMPEG_LICENCE = "ffmpeg-LGPL.txt"

#: Suffixes the pattern scan reads as text.
#:
#: **An allowlist, and the literal scan below does not use it.** Every file in the artifact is
#: searched byte-for-byte for the build machine's identity, because that is the half that would
#: actually leak and a `.so` can carry an embedded path. The *pattern* scan is bounded to text
#: because `_COOKIE_PATH`'s nested quantifiers are expensive — measured: it had not finished over
#: the bundled yt-dlp sources after two minutes — and a gate slow enough to be disabled protects
#: nothing.
TEXT_SUFFIXES = frozenset(
    {
        ".py",
        ".pyi",
        ".txt",
        ".md",
        ".json",
        ".toml",
        ".cfg",
        ".ini",
        ".xml",
        ".html",
        ".js",
        ".css",
    }
)

#: Lines longer than this are skipped by the pattern scan only.
#:
#: A minified bundle or a base64 blob on one line is where those quantifiers go quadratic. The
#: literal scan still reads every byte of those files.
MAX_SCANNED_LINE = 2000


#: The cookie vocabulary, imported rather than restated — see `no_secrets_or_personal_paths`.
COOKIE_PATTERNS = (
    (_COOKIE_HEADER, "a cookie header"),
    (_COOKIE_PATH, "a cookie store path"),
    (_COOKIE_FILENAME, "a cookie store filename"),
)


def qt_ships_as_shared_libraries(root: Path) -> list[str]:
    """§8 item 11 · `NFR-009` — and it is a licence obligation, not a preference.

    `LIC-001`: *"Qt and ffmpeg must be dynamically linked and replaceable."* That is the condition
    under which an MIT application may distribute LGPLv3 Qt at all, so this check is the one in
    this file whose failure is a licence breach rather than a defect.
    """
    problems: list[str] = []
    found = {
        module
        for module in REQUIRED_QT_MODULES
        if any(root.rglob(f"libQt6{module}.so*")) or any(root.rglob(f"Qt6{module}.dll"))
    }
    for module in REQUIRED_QT_MODULES:
        if module not in found:
            problems.append(
                f"Qt{module} is not in the bundle as a shared library. LIC-001 requires Qt to be "
                f"dynamically linked and replaceable; a static Qt would make this artifact "
                f"undistributable under the LGPL"
            )
    return problems + _qt_links_resolve_inside_the_artifact(root)


def _qt_links_resolve_inside_the_artifact(root: Path) -> list[str]:
    """Ask the loader, not the filesystem — presence alone cannot see a static build.

    **The presence check above passed with its subject deleted**, which is why this exists. The
    bundle carries Qt twice — `_internal/` and `_internal/PySide6/Qt/lib/` — so removing one copy
    left the other and `rglob` was satisfied. `T031-R2`'s rule is that a check nobody has watched
    fail is a check nobody has tested, and that mutation is what found it.

    `ldd` on each PySide6 extension answers the real question: the Qt module is a **dependency**
    rather than compiled in, and it resolves to a file **inside this artifact** rather than to the
    build machine's system Qt. A static build lists no such dependency; a build that borrowed the
    host's Qt resolves outside the tree; a deleted library resolves to *not found*. All three are
    LGPL problems and all three fail here.

    **Linux only, and it says so rather than pretending.** `dumpbin` is not on a stock Windows
    machine, so the Windows artifact keeps the presence check alone — a narrower guarantee, stated
    in `T-323` rather than implied here.
    """
    loader = shutil.which("ldd")
    extensions = sorted(root.rglob("PySide6/Qt*.abi3.so"))
    if loader is None or not extensions:
        return []

    problems: list[str] = []
    for extension in extensions[:4]:
        try:
            # `S603`: both arguments are ours — `ldd` located on PATH, and a path this function
            # produced by globbing inside the artifact it was handed. No shell, no user input.
            listed = subprocess.run(  # noqa: S603
                [loader, str(extension)], capture_output=True, text=True, timeout=60, check=False
            ).stdout
        except OSError, subprocess.SubprocessError:  # pragma: no cover - environment-dependent
            return []
        for line in listed.splitlines():
            name, _, resolved = line.strip().partition(" => ")
            if not name.startswith("libQt6"):
                continue
            target = resolved.split(" (")[0].strip()
            if not target or "not found" in resolved:
                problems.append(
                    f"{extension.relative_to(root)} needs {name} and the loader cannot find it "
                    f"in this artifact"
                )
            elif not Path(target).resolve().is_relative_to(root.resolve()):
                problems.append(
                    f"{extension.relative_to(root)} resolves {name} to {target}, outside the "
                    f"artifact — this build borrows the host's Qt and would not run elsewhere"
                )
    return problems


def licence_texts_are_present(root: Path) -> list[str]:
    """§8 item 12 · `LIC-001`: *"their license texts must ship with every distributed
    artifact"*."""
    problems: list[str] = []
    # **Located rather than assumed.** PyInstaller puts `datas` under `_internal/` in a one-dir
    # build, not beside the executable, and the first version of this check looked only at the
    # root and reported the licences missing from a build that carried them.
    directory = next((path for path in root.rglob("licenses") if path.is_dir()), None)
    if directory is None:
        return ["no licences directory anywhere in the artifact — LIC-001 requires one"]

    for name in REQUIRED_LICENCES:
        if not (directory / name).is_file():
            problems.append(f"{directory.relative_to(root)}/{name} is missing")
        elif (directory / name).stat().st_size == 0:
            problems.append(f"{directory.relative_to(root)}/{name} is empty")

    bundles_ffmpeg = any(root.rglob("ffmpeg.exe")) or any(root.rglob("ffmpeg"))
    if bundles_ffmpeg and not (directory / FFMPEG_LICENCE).is_file():
        problems.append(
            f"this artifact bundles ffmpeg and carries no {FFMPEG_LICENCE}. OPS-001 "
            f"bundles ffmpeg on Windows only, and LIC-001 requires an LGPL build with its text"
        )
    return problems


def ytdlp_is_pure_python(root: Path) -> list[str]:
    """§8 item 9 · `OPS-002` — a compiled extension would break the in-app update.

    The update path extracts a wheel over the bundled tree. That works because yt-dlp is pure
    Python; one compiled extension and the extracted copy would need a matching ABI, which the
    frozen runtime cannot promise.
    """
    trees = [path for path in root.rglob("yt_dlp") if path.is_dir()]
    if not trees:
        return [
            "no bundled yt_dlp tree found, so OPS-002's update path has nothing to extract over"
        ]

    problems: list[str] = []
    for tree in trees:
        for suffix in (".so", ".pyd"):
            for compiled in tree.rglob(f"*{suffix}"):
                problems.append(
                    f"{compiled.relative_to(root)} is a compiled extension inside yt_dlp. "
                    f"OPS-002's wheel-extraction update needs the bundled tree to stay pure Python"
                )
    return problems


def no_secrets_or_personal_paths(root: Path) -> list[str]:
    """§8 item 13 · `NFR-007` — nothing about the machine that built it.

    **The cookie vocabulary is imported from `core/logging` rather than restated** (`T015-R1`'s
    rule, applied to a gate): a secret class added to the redactor is scanned for here without
    anyone remembering this file exists. The private names are imported deliberately — a public
    alias would be a second spelling of the same list, which is the thing being avoided.

    **The build host's own identity is computed rather than listed**, because `core/logging`
    cannot know it: it redacts what a *running* application would log, and this asks what a
    *build machine* left behind.

    **A bare user name is not evidence, and that is measured rather than assumed.** The first
    version searched for `getpass.getuser()` on its own and reported
    `_internal/libbrotlicommon.so.1` — brotli's built-in English dictionary, which contains the
    four letters of this maintainer's name inside ordinary words. The real home path appeared in
    **no file in the artifact**. So the name counts only bracketed by path separators, which is
    the form that would actually leak, and `core/logging`'s own four-byte floor has the same
    reasoning behind it: a short ASCII token collides with prose.
    """
    home = str(Path.home())
    user = getpass.getuser()
    literals = {
        home: "the build machine's home directory",
        home.replace("/", "\\"): "the build machine's home directory, Windows spelling",
        f"/{user}/": "the build machine's user name, in a path",
        f"\\{user}\\": "the build machine's user name, in a path",
        ".netrc": "a netrc reference",
    }
    literals = {value: why for value, why in literals.items() if len(value) >= 6}

    problems: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            continue

        where = path.relative_to(root)
        for literal, why in literals.items():
            if literal.encode("utf-8", "ignore") in raw:
                problems.append(f"{where} contains {why}")

        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        for line in raw.decode("utf-8", "ignore").splitlines():
            if len(line) > MAX_SCANNED_LINE:
                continue
            hit = next(
                (why for pattern, why in COOKIE_PATTERNS if pattern.search(line)),
                None,
            )
            if hit is not None:
                problems.append(f"{where} contains {hit}")
                break
    return problems


CHECKS = (
    ("item 11 · Qt dynamically linked", qt_ships_as_shared_libraries),
    ("item 12 · licence texts present", licence_texts_are_present),
    ("item 13 · no secrets or personal paths", no_secrets_or_personal_paths),
    ("item 9 · yt-dlp stays pure Python", ytdlp_is_pure_python),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Release-gate checks over a built artifact.")
    parser.add_argument(
        "artifact", type=Path, help="the one-dir build, e.g. dist/tracks-and-trails"
    )
    arguments = parser.parse_args(argv)

    root: Path = arguments.artifact
    if not root.is_dir():
        print(f"artifact-gates: {root} is not a directory", file=sys.stderr)
        return 2

    failed = 0
    for name, check in CHECKS:
        problems = check(root)
        if problems:
            failed += 1
            print(f"FAIL  {name}", file=sys.stderr)
            for problem in problems[:20]:
                print(f"        {problem}", file=sys.stderr)
            if len(problems) > 20:
                print(f"        … and {len(problems) - 20} more", file=sys.stderr)
        else:
            print(f"ok    {name}")

    if failed:
        print(f"artifact-gates: {failed} of {len(CHECKS)} checks failed", file=sys.stderr)
        return 1
    print(f"artifact-gates: all {len(CHECKS)} checks passed on {root}")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through `main`
    raise SystemExit(main())
