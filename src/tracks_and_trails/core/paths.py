"""Filename sanitizing and output-path containment.

Enforces the intersection of Linux and Windows filesystem rules, and guarantees a
rendered template cannot escape the configured output directory (`ARCHITECTURE.md` §8).

**The security property, stated plainly: a title-derived filename must never escape the
configured output directory.** Titles come from media sites. They are attacker-influenced data
that reaches this module after yt-dlp renders them into a template, and `ARCHITECTURE.md` §9
already forbids them reaching a shell. This module is the other half: they must not reach a
path outside the directory the user chose either.

**Both platforms' rules, on both platforms.** `ai/TESTING.md` §7 requires Windows-illegal names
to be sanitized on Linux too. A file named `aux.mp4` or `what?.mp4` is legal on ext4 and
unopenable once the directory syncs to Windows, gets shared, or is restored onto another
machine — so the intersection is enforced everywhere rather than per-host. That is also why
this module takes no interest in `os.name`: identical input produces identical output on both
platforms, which is what makes it testable in CI on either.

**What this module does not do.** It does not render output templates — that uses yt-dlp's own
mechanism and belongs to `ytdlp_adapter.py` (`T-012`), the only code allowed to know that
syntax (`ARCHITECTURE.md` §6). It writes nothing. It answers one question: *given a candidate
path and a target directory, what is the safe path inside that directory, or is there none?*
"""

import hashlib
import unicodedata
from pathlib import Path, PureWindowsPath
from typing import Final

#: Characters NTFS forbids outright, plus the path separators of both platforms.
#:
#: `/` is included even though it is legal in a Windows *component* — by the time a title
#: reaches here it is a single component, so a separator inside it is an escape attempt, not a
#: directory the user asked for.
_ILLEGAL_CHARACTERS: Final = frozenset('<>:"/\\|?*')

#: Digits Windows accepts in a device name: `1` to `9` plus the three superscript forms.
#:
#: **`0` is deliberately absent.** Microsoft's list runs `COM1` to `COM9`, `COM¹`, `COM²`, `COM³`
#: and the matching `LPT` names — `COM0` and `LPT0` are *not* reserved. A correction pass added
#: them anyway, reasoning that auditing the class beat listing instances. That was wrong here:
#: the authority is explicit and finite, so there was no class to generalise, and the result
#: mangled two legal filenames while colliding with the very thing it produced — `COM0` became
#: `COM0_`, which is what a file legitimately named `COM0_` also sanitizes to. Fixing a
#: collision finding introduced a collision (`T034-R4`, second round).
#:
#: The superscripts are the part that *was* missing, and they are real.
_DEVICE_DIGITS: Final = "123456789¹²³"

#: Windows reserved device names. Reserved with **any** extension: `CON.mp4` is as unusable as
#: `CON`, which is the case usually missed — the check must run against the stem, not the name.
#:
#: Source: Microsoft, *Naming Files, Paths, and Namespaces*.
_RESERVED_NAMES: Final = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{digit}" for digit in _DEVICE_DIGITS}
    | {f"LPT{digit}" for digit in _DEVICE_DIGITS}
)

#: Substituted for anything illegal. A visible marker beats silent deletion: a user who sees
#: `Artist - Song_ Live.mp4` can tell something was replaced, where `Artist - Song Live.mp4`
#: looks like the title always was that.
_REPLACEMENT: Final = "_"

#: Used when sanitizing removes everything. Never an empty component.
_FALLBACK_STEM: Final = "download"

#: Conservative component limit. Most filesystems allow 255 *bytes*; a component of 255
#: astral-plane characters is 1020 bytes in UTF-8 and fails on ext4 while passing a naive
#: length check. Budgeting in encoded bytes is what makes this correct for emoji titles.
MAX_COMPONENT_BYTES: Final = 200

#: Conservative full-path limit. Windows' classic `MAX_PATH` is 260 including the drive and a
#: NUL; long-path support exists but is opt-in per machine and per API, so a released
#: application cannot assume it.
MAX_PATH_CHARACTERS: Final = 240


class UnsafePathError(Exception):
    """A path that cannot be made safe, rather than one that merely needed cleaning.

    Distinct from returning a sanitized value because the two demand different responses:
    sanitizing is routine and silent, while this means a caller asked for something outside the
    output directory and the request must fail loudly rather than be quietly redirected. A
    silent redirect would write a file somewhere the user was never told about.
    """


def _strip_control_characters(text: str) -> str:
    """Remove NUL and other control characters.

    NUL truncates the name at the C API boundary — `"clip\\x00.mp4"` becomes `"clip"` — so it
    is a way to change a filename after validation. The rest are unprintable and break tooling.
    """
    return "".join(char for char in text if unicodedata.category(char) != "Cc")


#: Bytes of digest appended to a truncated name.
#:
#: 8, not 4 (`T034-R2`, second round). Four bytes is 32 bits, so a birthday collision arrives
#: around 2^16 — the reviewer found a concrete pair at 96,718 candidates, which this project's
#: own acceptance criterion ("shortening must not collide with a neighbouring file") does not
#: permit. Eight bytes moves that to roughly 2^32 for the cost of eight more characters.
_MARKER_BYTES: Final = 8


def _marker(text: str) -> str:
    """A short, stable digest of `text`, used to keep truncated names distinct.

    `T034-R2`: prefix truncation alone collides. Two 401-character stems sharing their first
    400 characters produced the same 200-byte filename, so two different downloads would have
    fought over one path. The earlier collision test differed near the *start*, exactly where
    naive truncation already preserves the distinction, so it proved nothing.

    `blake2b` at 4 bytes is not a security choice — it is a short, deterministic, dependency-free
    way to carry the discarded tail's identity. Determinism matters because sanitizing must be
    idempotent and reproducible across processes and platforms.
    """
    return "-" + hashlib.blake2b(text.encode("utf-8"), digest_size=_MARKER_BYTES).hexdigest()


def _truncate_to_bytes(text: str, limit: int) -> str:
    """Shorten `text` to `limit` UTF-8 bytes, never splitting a character.

    A truncated result carries a digest of the original so two inputs sharing a prefix do not
    collapse onto one name. Text that already fits is returned untouched, which is what keeps
    the operation idempotent — a second pass sees a short string and changes nothing.
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text

    marker = _marker(text)
    budget = limit - len(marker.encode("utf-8"))
    if budget <= 0:
        # No room for both; the digest alone is more useful than an arbitrary prefix, because
        # it is what distinguishes this name from its neighbours.
        return marker[:limit]
    return encoded[:budget].decode("utf-8", errors="ignore").rstrip(". ") + marker


def sanitize_component(name: str) -> str:
    """Return `name` as a single path component that is legal on Linux **and** Windows.

    Deterministic and idempotent: `sanitize_component(sanitize_component(x))` equals
    `sanitize_component(x)` for every input. That is what lets a caller pass a path through
    twice — a preview and then the real write, say — without the second pass corrupting it.

    Order matters. Illegal characters are replaced before trailing dots and spaces are stripped,
    because replacing can expose a new trailing character; and the reserved-name check runs on
    the resulting stem, because `CON.mp4` is reserved while `CONCERT.mp4` is not.
    """
    cleaned = _strip_control_characters(name)
    cleaned = "".join(_REPLACEMENT if char in _ILLEGAL_CHARACTERS else char for char in cleaned)

    if not cleaned.strip(". ") or set(cleaned) <= {"."}:
        return _FALLBACK_STEM

    stem, dot, extension = cleaned.partition(".")

    # **Strip the stem before deciding reserved-ness**, not only at the end of the function.
    #
    # Windows discards trailing dots and spaces when creating a file, and matches a device name
    # ignoring them, so `"CON "` and `"CON .mp4"` *are* `CON` there. Testing the unstripped stem
    # let `"CON "` through undefused, and the final strip then produced a bare `"CON"` anyway —
    # an unopenable file. It also broke idempotence: a second pass saw `CON` and defused it, so
    # the `REQ-011` preview and the eventual write disagreed.
    #
    # One guard, not two. An earlier correction had a strip here *and* before this block, then
    # deleted one as "redundant" on mutation evidence — and the deletion caused this bug,
    # because no test covered a decorated reserved name. The tests now do, so the redundancy is
    # resolved deliberately rather than by mutation roulette: reverting this line fails them.
    #
    # The marker is taken over the *stripped* stem, so `"CON"` and `"CON "` produce one name.
    # That is correct — Windows considers them one file — and it is the only place this module
    # deliberately merges two inputs.
    stem = stem.rstrip(". ")
    if stem.upper() in _RESERVED_NAMES:
        # Suffixed with a digest, not a bare `_` (`T-045`). The user's title stays readable and
        # the result stays unique: `COM1` and a legal file named `COM1_` both produced `COM1_`,
        # so two distinct names landed on one path — the same collision class the truncation
        # differentiator exists to prevent, reached by a different route.
        #
        # A bare marker rather than `_` plus marker, so the defused name cannot be confused with
        # a truncated one. Idempotent: `COM1-<hex>` is not itself reserved, so a second pass
        # leaves it alone.
        stem = f"{stem}{_marker(stem)}"
    cleaned = f"{stem}{dot}{extension}"

    # The one place trailing dots and spaces are removed. Windows strips them when creating a
    # file, so `"clip. "` and `"clip"` would silently collide; stripping here makes that visible.
    # An earlier version also stripped before the reserved-name check, which mutation testing
    # showed was redundant — every case reaches this line anyway.
    return _truncate_to_bytes(cleaned, MAX_COMPONENT_BYTES).rstrip(". ") or _FALLBACK_STEM


def sanitize_filename(name: str) -> str:
    """Sanitize a filename, preserving its extension when shortening.

    Truncating a name to a byte budget can eat the extension, which changes what the file *is*
    to every tool that reads one. The stem is shortened instead, and the extension is kept.

    **The split happens before any truncation**, on the raw name. Sanitizing first and splitting
    afterwards loses the extension whenever the stem alone exceeds the budget — the component
    truncation has already removed it by the time the split runs. Both length tests failed on
    exactly that ordering.
    """
    raw_stem, dot, raw_extension = name.rpartition(".")
    if not dot or not raw_extension or len(raw_extension) > 20:
        # No usable extension: `.bashrc` (empty stem), no dot at all, or something too long to
        # be one — a title containing a full stop is far likelier than a 20-character suffix.
        return sanitize_component(name)

    extension = sanitize_component(raw_extension).rstrip(". ")
    if not extension:
        return sanitize_component(name)

    suffix = f".{extension}"
    budget = MAX_COMPONENT_BYTES - len(suffix.encode("utf-8"))
    if budget <= 0:
        return sanitize_component(name)

    stem = _truncate_to_bytes(sanitize_component(raw_stem), budget).rstrip(". ")
    return f"{stem or _FALLBACK_STEM}{suffix}"


def _components(candidate: str) -> list[str]:
    """Split `candidate` on **both** platforms' separators, whatever the host is.

    Reading a Windows-style path with POSIX rules is how `..\\..\\evil` survives as a single
    component on Linux, only to become traversal once the name reaches a Windows machine. Both
    separators are honoured so neither host's rules can hide the other's escape.

    Deliberately a string split rather than `PurePosixPath`/`PureWindowsPath`. An earlier
    version parsed with both and took whichever produced more parts; mutation testing showed
    that was dead code — normalising the separator first makes the path classes redundant here,
    and this is far easier to reason about at a security boundary.

    Empty pieces are dropped, which is what neutralises a leading `/` (absolute) and a leading
    `\\\\` (UNC) without either needing a special case.
    """
    return [piece for piece in candidate.replace("\\", "/").split("/") if piece]


def is_contained(path: Path, directory: Path) -> bool:
    """Whether `path` resolves inside `directory`.

    Compares **resolved** paths, so a symlink inside the output directory pointing elsewhere
    does not pass. `Path.resolve()` is used rather than string prefixing because
    `/home/user/Downloads-evil` starts with `/home/user/Downloads` as a string while being a
    different directory entirely.
    """
    try:
        resolved = path.resolve()
        base = directory.resolve()
    except OSError:
        return False
    return resolved == base or base in resolved.parents


def escapes_directory(candidate: str) -> bool:
    """Whether `candidate` *tries* to leave the directory it will be joined to (`T012-R4`).

    Distinct from `safe_output_path`, which **neutralizes** an escape by dropping the offending
    components. Neutralizing is right for a filename derived from a title the user did not
    choose: a video called `../../etc/passwd` should still download, just safely.

    It is wrong for the *output template*, which the user typed. `T-012`'s criterion is that a
    template rendering outside the target directory is "rejected, not written", and silently
    rewriting `../elsewhere/%(title)s.%(ext)s` into a file in the chosen folder tells the user
    their template worked when it did not. Detecting intent and refusing is the honest answer;
    this function is the detection half.

    Both separators are examined regardless of host, for the reason `_components` explains: a
    Windows-style escape must not survive being read with POSIX rules.
    """
    if not candidate:
        return False
    normalised = candidate.replace("\\", "/")
    pure = PureWindowsPath(normalised)
    # A drive (`C:`) or a root (`/`, and `//host/share` after normalisation) is absolute intent.
    if pure.drive or pure.root:
        return True
    return any(part == ".." for part in normalised.split("/"))


def safe_output_path(directory: Path, candidate: str) -> Path:
    """Return the sanitized path for `candidate` inside `directory`, or raise `UnsafePathError`.

    The single entry point `ARCHITECTURE.md` §8 requires every output path to pass through.
    `T-012` calls it on whatever yt-dlp's template renderer produced, before that path is used.

    Traversal is **neutralized, not escaped**: `..` components are dropped rather than replaced
    with a literal `..` string, absolute roots and drive letters are discarded so the path stays
    relative to `directory`, and UNC prefixes cannot survive because their separators are
    stripped during component splitting.

    Raises rather than silently redirecting when nothing usable survives, or when the result
    somehow still falls outside `directory` — the belt-and-braces check at the end. A silent
    redirect writes a file somewhere the user was never told about.
    """
    if not candidate or not _strip_control_characters(candidate).strip():
        raise UnsafePathError("empty candidate path")

    raw_parts: list[str] = []
    for index, part in enumerate(_components(candidate)):
        # A drive letter or root is discarded, not sanitized into a directory name: the user
        # asked for a file in `directory`, and `C:` becoming a folder called `C_` would be a
        # surprising interpretation of an absolute path.
        if part in (".", "", ".."):
            continue
        # Drop a component that *is* a drive specifier (`C:` from `C:\\Windows\\evil.mp4`).
        #
        # A component that merely *begins* with one is sanitized normally instead of discarded:
        # `"A: The Movie.mp4"` is a perfectly ordinary title, and rejecting the whole candidate
        # meant a legal download failed outright. The colon is illegal anyway, so it becomes
        # `"A_ The Movie.mp4"` — the same treatment `"Artist: Song.mp4"` already got, and
        # equally contained.
        if index == 0 and PureWindowsPath(part).drive == part:
            continue
        raw_parts.append(part)

    if not raw_parts:
        raise UnsafePathError(f"nothing usable remained of {candidate!r}")

    # The final component goes through `sanitize_filename` on its **raw** value, so the
    # extension is split off before any truncation. Sanitizing it as a component first would
    # have already discarded the suffix.
    safe_parts = [sanitize_component(part) for part in raw_parts[:-1]]
    safe_parts.append(sanitize_filename(raw_parts[-1]))
    result = directory.joinpath(*safe_parts)

    # Shorten from the *stem* if the assembled path is too long, so the extension and the
    # directory structure both survive.
    if len(str(result)) > MAX_PATH_CHARACTERS:
        room = MAX_PATH_CHARACTERS - len(str(result.parent)) - 1
        if room <= 0:
            raise UnsafePathError(
                f"output directory {str(directory)!r} leaves no room for a filename "
                f"within {MAX_PATH_CHARACTERS} characters"
            )
        result = result.parent / _shorten_to(result.name, room)

    # **Reachable, and load-bearing** (`T034-R1`). An earlier comment here claimed no input
    # could reach this raise. That was wrong: neutralising the *candidate string* says nothing
    # about the *filesystem*, and an existing symlink under the output directory pointing
    # outside it makes the joined path resolve elsewhere. `safe_output_path(out, "link/clip.mp4")`
    # raises here when `out/link` is such a symlink.
    #
    # The mutation that "proved" it dead only looked green because no test drove a symlink
    # through this entry point — `is_contained()` was tested directly instead. It is now driven
    # from here, and removing this branch fails the suite.
    if not is_contained(result, directory):
        raise UnsafePathError(f"{candidate!r} would write outside {str(directory)!r}")
    return result


def numbered_variant(path: Path, index: int) -> Path:
    """`clip.mp4` at index 2 becomes `clip (2).mp4` — the next candidate when a path is taken.

    **Pure, and it stays pure** (`DAT-002`). This says what the *n*th alternative to a path is
    called; it does not know or ask whether any of them exists. "Does this collide?" is a
    question about the filesystem, and `DAT-002` moved that to `T-046` at the layer holding
    filesystem context precisely so this module would not become stateful.

    ` (2)` rather than a digest or a timestamp: it is the convention every desktop file manager
    uses for the same situation, so a second copy of a video is recognisable as one. `T-045`'s
    digest exists to keep *distinct* inputs apart, which is a different problem — here the
    inputs really are the same name and the user needs to see which is which.

    The extension survives, and the **marker survives too**: the stem is what gets shortened
    when the budgets bite. Trimming the marker instead would produce two candidates with the
    same name, which is the one thing this function exists to prevent. `_shorten_to`'s
    reasoning applies to the extension for the same reason it does there.
    """
    if index < 2:
        raise ValueError(f"a numbered variant starts at 2, not {index}")

    marker = f" ({index})"
    suffix = path.suffix if path.suffix and len(path.suffix) <= 21 else ""
    stem = path.name[: len(path.name) - len(suffix)] or _FALLBACK_STEM

    byte_room = MAX_COMPONENT_BYTES - len((marker + suffix).encode("utf-8"))
    if byte_room < 1:
        raise UnsafePathError(
            f"no room for {path.name!r} plus {marker!r} within {MAX_COMPONENT_BYTES} bytes"
        )
    stem = _truncate_to_bytes(stem, byte_room).rstrip(". ")

    result = path.with_name(f"{stem or _FALLBACK_STEM}{marker}{suffix}")
    if len(str(result)) <= MAX_PATH_CHARACTERS:
        return result

    # The whole path is too long, which the directory can cause on its own. Shorten the stem
    # again, against characters this time — the two budgets are different units and a name can
    # satisfy one while breaking the other.
    character_room = MAX_PATH_CHARACTERS - len(str(path.parent)) - 1 - len(marker) - len(suffix)
    if character_room < 1:
        raise UnsafePathError(
            f"output directory {str(path.parent)!r} leaves no room for {path.name!r} plus "
            f"{marker!r} within {MAX_PATH_CHARACTERS} characters"
        )
    stem = stem[:character_room].rstrip(". ")
    return path.with_name(f"{stem or _FALLBACK_STEM}{marker}{suffix}")


def _shorten_to(name: str, limit: int) -> str:
    """Shorten `name` to `limit` characters, keeping its extension.

    Raises `UnsafePathError` when the extension cannot fit (`T034-R3`). The earlier fallback
    returned `name[:limit]`, so a directory leaving two characters turned `clip.mp4` into `cl` —
    an extensionless path that every tool reading the file would misidentify, produced silently
    while the acceptance criterion says shortening keeps the extension. Failing is the honest
    outcome: the user picked a directory too deep for the name, and can be told so.
    """
    if len(name) <= limit:
        return name

    stem, dot, extension = name.rpartition(".")
    suffix = f".{extension}" if dot else ""
    marker = _marker(name)
    room = limit - len(suffix) - len(marker)
    if not dot:
        if limit - len(marker) < 1:
            raise UnsafePathError(f"no room to shorten {name!r} to {limit} characters")
        return name[: limit - len(marker)].rstrip(". ") + marker
    if room < 1:
        raise UnsafePathError(
            f"no room for {name!r} within {limit} characters while keeping {suffix!r}"
        )
    return f"{stem[:room].rstrip('. ') or _FALLBACK_STEM}{marker}{suffix}"
