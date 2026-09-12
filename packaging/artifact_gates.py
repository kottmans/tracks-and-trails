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
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tracks_and_trails.core.logging import (
    _COOKIE_FILENAME,
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

#: How much decoded text the **costly** patterns read from one file before reporting that they
#: stopped. **Truncation is reported as a problem**, so a bound can never quietly become a gap
#: (`T323-R2`).
#:
#: It is a bound on work, not a cost control: see `COSTLY_PATTERNS` for why truncating does not
#: rescue those patterns, which is why they are kept off binaries entirely rather than capped.
MAX_SCANNED_BYTES = 2_000_000


#: Credentials inside a URL, in **this medium's** form.
#:
#: `core/logging`'s `_BARE_USERINFO` is deliberately for userinfo with **no scheme** — its
#: lookbehind excludes a preceding `/`, because a full URL is `_URL`'s job there. Pointed at an
#: artifact it matches package specifiers: `npm:meriyah@6.1.4` in yt-dlp's bundled solver, measured.
#: So the class is covered by the shape it actually takes in a shipped file, a scheme followed by
#: `user:pass@`, and the reason for not reusing the redactor's pattern is that it is for prose.
_URL_CREDENTIALS = re.compile(r"[a-zA-Z][\w+.\-]*://[^\s/@:]+:[^\s/@]+@")

#: A cookie header **carrying a cookie**, rather than the word in a format string.
#:
#: `_COOKIE_HEADER` matches `Received cookie: {lenstr}` in `libkrb5.so.3` — correctly, for a log
#: line, where that is about to be filled in with one. In an artifact a format string is not a
#: leak, so the value has to look like `name=value`.
_COOKIE_WITH_A_VALUE = re.compile(
    r"\b(?:set-)?cookie\s*:\s*[^\n\r{%]*[A-Za-z0-9_.\-]+=[^\s;{%]+", re.IGNORECASE
)

#: Patterns cheap enough to run over **every** file, binaries included.
#:
#: Both are linear. Measured over this artifact's 337 binary files (206 MB of Qt, CPython and
#: ffmpeg): `_COOKIE_WITH_A_VALUE` 10.7s, `_URL_CREDENTIALS` 13.2s, no false positives. That is
#: what a release gate can afford, and it is what closes the hole `T323-R2` found — planted
#: cookie material in a file that is not named like text.
CHEAP_PATTERNS = (
    (_COOKIE_WITH_A_VALUE, "a cookie header carrying a value"),
    (_URL_CREDENTIALS, "credentials inside a URL"),
)

#: The redactor's own cookie-store patterns, which run over **text only**.
#:
#: Both have nested quantifiers that go quadratic on binary noise. Measured on one library,
#: `libQt6Gui.so.6`: `_COOKIE_FILENAME` takes **171 seconds**. Truncating to `MAX_SCANNED_BYTES`
#: does not rescue them — the same file capped to two megabytes still took 170.7s, because the
#: blow-up happens inside the first two megabytes — so the split is by file kind, not by size.
#:
#: **This is a stated bound, not a silent one.** A cookie *store* planted inside a compiled
#: binary would not be found by these two. It would still be found by the byte markers below,
#: which do run over every file, and by `_COOKIE_WITH_A_VALUE` above if it carries a header.
COSTLY_PATTERNS = (
    (_COOKIE_PATH, "a cookie store path"),
    (_COOKIE_FILENAME, "a cookie store filename"),
)

#: Kept so a caller can ask for the whole vocabulary without knowing the cost split.
CONTENT_PATTERNS = CHEAP_PATTERNS + COSTLY_PATTERNS


def qt_ships_as_shared_libraries(root: Path) -> list[str]:
    """§8 item 11 · `NFR-009` — and it is a licence obligation, not a preference.

    `LIC-001`: *"Qt and ffmpeg must be dynamically linked and replaceable."* That is the condition
    under which an MIT application may distribute LGPLv3 Qt at all, so this check's failure is a
    licence breach rather than a defect.

    **Three ways this has been wrong, all found by review rather than by the check** (`T323-R1`):

    1. It globbed for the library files and passed with `libQt6Widgets.so.6` deleted, because the
       bundle carries Qt at two paths. The *second* is a **symlink, not an independent copy** — the
       earlier note here said otherwise — so a dangling link satisfied a glob.
    2. The loader half then inspected `extensions[:4]`, an arbitrary cap. QtWidgets sorts fifth in
       a real build, so the one module the mutation removed was the one never asked about.
    3. An inspection that could not run — no `ldd`, a failed call — returned *no problems*, which
       is indistinguishable from *no problem found*.

    So: every required module must resolve to a **real file inside the artifact**, and every
    binding is inspected. An inspection that cannot be performed is reported, never passed over.
    """
    problems: list[str] = []
    for module in REQUIRED_QT_MODULES:
        # `is_file()` follows the link, so a dangling symlink is not a library.
        usable = [
            path
            for pattern in (f"libQt6{module}.so*", f"Qt6{module}.dll")
            for path in root.rglob(pattern)
            if path.is_file()
        ]
        if not usable:
            dangling = [p for p in root.rglob(f"libQt6{module}.so*") if p.is_symlink()]
            detail = f" — {len(dangling)} dangling symlink(s) point at nothing" if dangling else ""
            problems.append(
                f"Qt{module} is not in the bundle as a usable shared library{detail}. LIC-001 "
                f"requires Qt to be dynamically linked and replaceable; a static or absent Qt "
                f"would make this artifact undistributable under the LGPL"
            )
    return problems + _qt_links_resolve_inside_the_artifact(root)


def _qt_links_resolve_inside_the_artifact(root: Path) -> list[str]:
    """Ask the loader, not the filesystem — presence alone cannot see a static build.

    `ldd` on each PySide6 binding answers the real question: the Qt module is a **dependency**
    rather than compiled in, and it resolves to a file **inside this artifact** rather than to the
    host's system Qt. A static build lists no such dependency; a build that borrowed the host's Qt
    resolves outside the tree; a deleted library resolves to *not found* — or, worse, silently to
    the system copy, which `T323-R1` observed doing exactly that and reporting incompatible
    private Qt symbols.

    **Windows keeps the presence check alone, and that is a narrower guarantee stated rather than
    implied.** `dumpbin` is not on a stock Windows machine and no equivalent ships with it, so
    item 11 on Windows establishes that the libraries are present and not that anything links to
    them. `T-323` records that disposition; this function does not pretend otherwise.
    """
    extensions = sorted(root.rglob("PySide6/Qt*.abi3.so"))
    if not extensions:
        if any(root.rglob("PySide6/Qt*.pyd")):
            return []  # Windows: the presence check above is the whole of item 11 there.
        return [
            "no PySide6 bindings found to inspect, so the linkage half of item 11 checked nothing"
        ]

    loader = shutil.which("ldd")
    if loader is None:
        return [
            "ldd is not available, so Qt's linkage could not be inspected. An inspection that "
            "cannot run is not a pass (T323-R1)"
        ]

    problems: list[str] = []
    evidenced: set[str] = set()
    for extension in extensions:
        try:
            # `S603`: both arguments are ours — `ldd` located on PATH, and a path this function
            # produced by globbing inside the artifact it was handed. No shell, no user input.
            listed = subprocess.run(  # noqa: S603
                [loader, str(extension)],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as failure:
            problems.append(f"could not inspect {extension.relative_to(root)}: {failure!r}")
            continue
        if listed.returncode != 0:
            problems.append(
                f"ldd failed on {extension.relative_to(root)}: {listed.stderr.strip()[:120]}"
            )
            continue

        for line in listed.stdout.splitlines():
            name, _, resolved = line.strip().partition(" => ")
            if not name.startswith("libQt6"):
                continue
            module = name.removeprefix("libQt6").split(".so")[0]
            target = resolved.split(" (")[0].strip()
            where = extension.relative_to(root)
            if not target or "not found" in resolved:
                problems.append(f"{where} needs {name} and the loader cannot find it")
            elif not Path(target).resolve().is_relative_to(root.resolve()):
                problems.append(
                    f"{where} resolves {name} to {target}, outside the artifact — this build "
                    f"borrows the host's Qt and would not run elsewhere"
                )
            else:
                evidenced.add(module)

    # **Positive linkage evidence, per module.** Without this, a build whose bindings happened to
    # declare no Qt dependency at all would produce no problems and no evidence, and pass.
    for module in REQUIRED_QT_MODULES:
        if module not in evidenced:
            problems.append(
                f"no binding in this artifact resolves libQt6{module} to a file inside it, so "
                f"nothing establishes that Qt{module} is dynamically linked here"
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


#: Files a **redistributed interpreter** owns, which PyInstaller copies in byte-for-byte.
#:
#: Named by shape rather than by a list of versions, because the version moves.
#: `libpython3.14.so.1.0` and `python3.14/lib-dynload/_bz2.cpython-314-x86_64-linux-gnu.so` are
#: the two forms measured in a real build (`T323-R4`); `python3.dll` and `DLLs/` are the Windows
#: spellings.
def is_interpreter_owned(where: Path) -> bool:
    """Whether `where` (relative to the artifact root) is part of the bundled interpreter.

    **Deliberately narrow.** It is not *"anything under `_internal`"* — that is the whole bundle,
    including this application's own code and yt-dlp's. It is the CPython runtime and its
    extension modules, which are the files that carry the paths CPython was built at.
    """
    parts = where.as_posix().split("/")
    if where.name.startswith(("libpython", "python3.dll")):
        return True
    return "lib-dynload" in parts or "DLLs" in parts


def no_secrets_or_personal_paths(root: Path) -> list[str]:
    """§8 item 13 · `NFR-007` — nothing about the machine that built it, and no cookie material.

    **Every file is read, and every file is scanned** (`T323-R2`). The first version scanned
    patterns only in an allowlist of text suffixes and skipped lines past column 2000, so a
    `Cookie:` header planted in a `.bin`, in an extensionless file, or on a long line all
    survived. Nothing is skipped by suffix now, and nothing is skipped by line length.

    What differs between a binary and a text file is only **which half of the vocabulary** runs —
    `CHEAP_PATTERNS` over everything, `COSTLY_PATTERNS` over text — and that split is by measured
    cost, recorded on those two constants. Where a bound applies it is **reported** rather than
    applied silently.

    **Filenames count as much as contents.** A populated `cookies.txt` in the artifact is a leak
    whatever is inside it, and the earlier version only ever looked at bytes.

    **What is scanned, and what deliberately is not.** The cookie and credential vocabulary is
    imported from `core/logging` rather than restated, so a class added to the redactor is scanned
    for here (`T015-R1`). Two of the redactor's classes are **out of scope here, by argument**:

    - **URL query values.** `redact` strips them because a *log line* quoting a URL may carry a
      token. An artifact legitimately contains thousands of URLs — yt-dlp's extractors are made of
      them — and flagging those would make this gate unreadable, which is how a gate gets
      disabled. Credentials *inside* a URL (`user:pass@host`) are a different class and **are**
      scanned for.
    - **Literals registered at runtime** by `remember_a_secret`. A static artifact has no runtime,
      so the registry is empty by construction; there is nothing to compare against.

    The earlier docstring claimed the complete vocabulary and implemented three patterns, which is
    the claim `T323-R2` corrected.
    """
    home = str(Path.home())
    user = getpass.getuser()

    #: **A redistributed interpreter's own paths are provenance, not a leak** (`T323-R3`, and
    #: `T323-R4` which is why this is a second attempt).
    #:
    #: `frozen linux` failed on **110** hits, every one inside `libpython3.14.so.1.0` or
    #: `lib-dynload/*.so`. The first fix exempted `sys.base_prefix` — the path the interpreter is
    #: *installed* at — and it did not work, because **that is not the path in the binary**.
    #: CPython embeds the directory it was **built** in, in `__FILE__` strings, `sysconfig` data
    #: and debug sections. Whoever built that CPython did so somewhere, and if they did it in a
    #: home directory then every copy of it quotes one for ever. The measured run reported *both*
    #: the home literal and the user-name-in-a-path literal, which the prefix exemption did not
    #: cover at all.
    #:
    #: **So the exemption is by file, and only for the path literals.** These files are copied
    #: into the bundle byte-for-byte by PyInstaller; nothing this project does writes to them, so
    #: a path inside one is a fact about a dependency rather than about this build.
    #:
    #: **What that gives up, stated rather than implied:** a personal path that existed *only*
    #: inside the bundled interpreter would not be reported. Nothing in this project can put one
    #: there — we copy the file, we do not author it — and the alternative measured worse: the
    #: gate failed every CI build, which is how a gate gets switched off.
    #:
    #: **Cookie material and URL credentials are still scanned in these files**, because those
    #: would *not* be explained by provenance. Only the two path literals are excused here.
    interpreter_prefix = str(Path(sys.base_prefix).resolve())

    literals: dict[str, str] = {
        home: "the build machine's home directory",
        home.replace("/", "\\"): "the build machine's home directory, Windows spelling",
        f"/{user}/": "the build machine's user name, in a path",
        f"\\{user}\\": "the build machine's user name, in a path",
        ".netrc": "a netrc reference",
    }
    literals = {value: why for value, why in literals.items() if len(value) >= 6}

    #: The literals the interpreter exemption covers: paths, and nothing else. `.netrc` is
    #: deliberately outside it — a netrc reference is not explained by where CPython was built.
    path_literals = frozenset(
        value
        for value in (home, home.replace("/", "\\"), f"/{user}/", f"\\{user}\\")
        if len(value) >= 6
    )

    #: Cheap, linear byte searches over **every** file, binary included. Deliberately distinctive:
    #: a bare `cookie:` matched a Kerberos format string in `libkrb5.so.3`, so the header form is
    #: left to `_COOKIE_WITH_A_VALUE` over decoded text and only unambiguous markers run here.
    markers: tuple[tuple[bytes, str], ...] = (
        (b"# netscape http cookie file", "a Netscape cookie store"),
        (b"# http cookie file", "a Netscape cookie store"),
    )

    problems: list[str] = []
    truncated: list[str] = []
    exempted = 0

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        where = path.relative_to(root)

        # A cookie store is a leak by its name, whatever it holds.
        if _COOKIE_FILENAME.search(path.name):
            problems.append(f"{where} is named as a cookie store")

        try:
            raw = path.read_bytes()
        except OSError as failure:
            # An unreadable file is not a clean file. `T323-R1`'s lesson, one check over.
            problems.append(f"{where} could not be read, so it was not scanned: {failure!r}")
            continue

        lowered = raw.lower()
        for marker, why in markers:
            if marker in lowered:
                problems.append(f"{where} contains {why}")

        interpreter_owned = is_interpreter_owned(where)
        for literal, why in literals.items():
            if literal.encode("utf-8", "ignore") not in raw:
                continue
            if literal in path_literals and interpreter_owned:
                # Provenance of a dependency we copy rather than author (`T323-R4`).
                exempted += 1
                continue
            if literal == home and interpreter_prefix.startswith(home):
                # A non-interpreter file may still legitimately quote the install prefix — a
                # `sysconfig` dump, say. Strip that one string and ask whether `home` survives.
                remaining = raw.replace(interpreter_prefix.encode("utf-8", "ignore"), b"")
                if literal.encode("utf-8", "ignore") not in remaining:
                    exempted += 1
                    continue
            problems.append(f"{where} contains {why}")

        # The regex half, over text decoded from the same bytes — **no suffix allowlist**, which
        # is what lets an extensionless file and a `.bin` be scanned (`T323-R2`). Whether a file
        # is text is decided by content, a NUL byte in the first block, and it selects only which
        # *half* of the vocabulary runs, never whether the file is scanned at all.
        text = raw.decode("utf-8", "ignore")
        found = next((why for pattern, why in CHEAP_PATTERNS if pattern.search(text)), None)

        if found is None and b"\x00" not in raw[:4096]:
            bounded = text[:MAX_SCANNED_BYTES]
            if len(text) > MAX_SCANNED_BYTES:
                truncated.append(str(where))
            found = next((why for pattern, why in COSTLY_PATTERNS if pattern.search(bounded)), None)

        if found is not None:
            problems.append(f"{where} contains {found}")

    if truncated:
        # **Reported, never silent** (`T323-R2`). A bound that nobody can see is a gap.
        problems.append(
            f"{len(truncated)} text file(s) were larger than {MAX_SCANNED_BYTES} bytes, so the "
            f"costly half of the pattern scan stopped early on them: "
            f"{', '.join(sorted(truncated)[:5])}. The byte searches and CHEAP_PATTERNS covered "
            f"them in full; raise the bound or split them"
        )
    if exempted:
        # **Reported, never silent.** An exemption nobody can see is indistinguishable from a
        # check that never ran, which is the shape of every finding this gate has had.
        print(
            f"      note: {exempted} path literal(s) excused as provenance — the bundled "
            f"interpreter's own files, and the install prefix {interpreter_prefix} "
            f"(T323-R3, T323-R4)"
        )
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
