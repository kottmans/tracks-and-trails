"""Filename safety and output-path containment (`T-034`, `ai/TESTING.md` §7).

§7 lists path safety as mandatory coverage, and states the property as: *no rendered output
template escapes the output directory; Windows-illegal names are sanitized on both platforms.*

The inputs here are hostile on purpose. Titles come from media sites, so every traversal
attempt, reserved device name and control character below is data the application will
genuinely be handed — not a contrived edge case. §5 requires fixtures covering NTFS-illegal
characters, reserved names, trailing dots and spaces, emoji, RTL text, and traversal.

**Every containment test asserts the result is inside the directory**, rather than asserting a
particular sanitized spelling. Pinning the spelling would make the suite fail on a harmless
change to the replacement character while still passing if containment broke.
"""

from pathlib import Path

import pytest

from tracks_and_trails.core.paths import (
    MAX_COMPONENT_BYTES,
    MAX_PATH_CHARACTERS,
    UnsafePathError,
    is_contained,
    safe_output_path,
    sanitize_component,
    sanitize_filename,
)

#: Traversal and absolute-path attempts. Each must be **neutralized**, not merely escaped into
#: a literal `..` component that a later path join could still interpret.
ESCAPE_ATTEMPTS = [
    "../evil.mp4",
    "../../../../etc/passwd",
    "..\\..\\windows\\system32\\evil.mp4",
    "/etc/passwd",
    "/absolute/clip.mp4",
    "C:\\Windows\\System32\\evil.mp4",
    "C:/Windows/evil.mp4",
    "\\\\server\\share\\evil.mp4",
    "//server/share/evil.mp4",
    "....//....//evil.mp4",
    "subdir/../../escape.mp4",
    "clip/../../../evil.mp4",
]

#: `ai/TESTING.md` §5's required fixture set.
HOSTILE_TITLES = [
    'Artist - Song: "Live" <2024>',
    "What?! | Really* | Yes",
    "CON",
    "CON.mp4",
    "aux.mp4",
    "LPT1.mkv",
    "nul",
    "trailing dots...",
    "trailing spaces   ",
    "mixed. . .",
    "🎵 Music 🎬 Video 🎸",
    "مرحبا بالعالم",
    "Ünïcödé Nörmalïzatïön",
    "clip\x00.mp4",
    "tab\tand\nnewline",
    ".",
    "..",
    "...",
]


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    target = tmp_path / "Downloads"
    target.mkdir()
    return target


# --- containment: the security property ------------------------------------------------------


@pytest.mark.parametrize("candidate", ESCAPE_ATTEMPTS)
def test_no_escape_attempt_leaves_the_output_directory(output_dir: Path, candidate: str) -> None:
    """The property `ai/TESTING.md` §7 makes mandatory.

    A title-derived path must never resolve outside the directory the user chose. Asserted on
    the *resolved* path, because string prefixing would accept a sibling directory whose name
    merely starts with the same characters.
    """
    result = safe_output_path(output_dir, candidate)
    assert is_contained(result, output_dir), f"{candidate!r} escaped to {result}"
    assert ".." not in result.parts, "traversal was escaped into a literal component, not removed"


@pytest.mark.parametrize("title", HOSTILE_TITLES)
def test_hostile_titles_stay_inside_the_output_directory(output_dir: Path, title: str) -> None:
    result = safe_output_path(output_dir, f"{title}.mp4")
    assert is_contained(result, output_dir)


def test_a_sibling_directory_with_a_shared_prefix_is_not_contained(tmp_path: Path) -> None:
    """`/…/Downloads-evil` starts with `/…/Downloads` as a string but is a different directory.

    This is why containment compares resolved paths rather than string prefixes.
    """
    (tmp_path / "Downloads").mkdir()
    sibling = tmp_path / "Downloads-evil"
    sibling.mkdir()
    assert not is_contained(sibling / "clip.mp4", tmp_path / "Downloads")


def test_a_symlink_out_of_the_directory_is_not_contained(tmp_path: Path) -> None:
    """A symlink inside the output directory pointing elsewhere is still an escape.

    The file would be written outside the directory the user chose, which is the property, not
    the spelling of the path.
    """
    target = tmp_path / "Downloads"
    target.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (target / "link").symlink_to(outside)
    assert not is_contained(target / "link" / "clip.mp4", target)


def test_an_ordinary_subdirectory_is_allowed(output_dir: Path) -> None:
    """Containment must not be so strict that legitimate templates break.

    Output templates routinely produce `%(uploader)s/%(title)s.%(ext)s`.
    """
    result = safe_output_path(output_dir, "Some Channel/Some Video.mp4")
    assert is_contained(result, output_dir)
    assert result.parent.name == "Some Channel"
    assert result.name == "Some Video.mp4"


@pytest.mark.parametrize("candidate", ["", "   ", "\x00", ".", "..", "../..", "/", "C:\\"])
def test_candidates_with_nothing_usable_raise(output_dir: Path, candidate: str) -> None:
    """Raise rather than silently redirect.

    A silent fallback writes a file somewhere the user was never told about, which is worse
    than a failed download they can see.
    """
    with pytest.raises(UnsafePathError):
        safe_output_path(output_dir, candidate)


# --- Windows rules, enforced on both platforms ----------------------------------------------


@pytest.mark.parametrize("char", list('<>:"/\\|?*'))
def test_every_ntfs_illegal_character_is_replaced(char: str) -> None:
    """Enforced on Linux too (`ai/TESTING.md` §7).

    A name legal on ext4 that becomes unopenable when the directory syncs to Windows is still a
    defect — the file has already been written by then.
    """
    assert char not in sanitize_component(f"clip{char}name.mp4")


@pytest.mark.parametrize(
    "name", ["CON", "con", "CoN", "CON.mp4", "aux.mkv", "NUL.webm", "COM1.mp4", "LPT9.mp3"]
)
def test_reserved_device_names_are_defused_including_with_extensions(name: str) -> None:
    """`CON.mp4` is as unusable as `CON` on Windows — the case usually missed.

    The check must run on the stem, not the whole name.
    """
    result = sanitize_component(name)
    stem = result.partition(".")[0]
    assert stem.upper() not in {"CON", "AUX", "NUL", "COM1", "LPT9"}


@pytest.mark.parametrize("name", ["CONCERT.mp4", "AUXILIARY.mkv", "NULL_POINTER.mp4", "COMET.mp4"])
def test_names_merely_starting_with_a_reserved_word_are_untouched(name: str) -> None:
    """The rule is exact-match on the stem. Mangling `CONCERT.mp4` would be a false positive."""
    assert sanitize_component(name) == name


@pytest.mark.parametrize("name", ["clip.", "clip ", "clip. ", "clip...", "clip   "])
def test_trailing_dots_and_spaces_are_stripped(name: str) -> None:
    """Windows strips these when creating a file, so `"clip. "` and `"clip"` silently collide.

    Stripping here makes the collision visible rather than surprising.
    """
    result = sanitize_component(name)
    assert not result.endswith((".", " "))


def test_control_characters_including_nul_are_removed() -> None:
    """NUL truncates a name at the C API boundary, so it can change a filename after checking."""
    assert "\x00" not in sanitize_component("clip\x00.mp4")
    assert "\t" not in sanitize_component("tab\there.mp4")
    assert "\n" not in sanitize_component("new\nline.mp4")


def test_emoji_and_rtl_text_survive() -> None:
    """These are legal on both platforms. Sanitizing must not mangle a legitimate title."""
    assert "🎵" in sanitize_component("🎵 Music.mp4")
    assert "مرحبا" in sanitize_component("مرحبا.mp4")


# --- determinism and idempotence -------------------------------------------------------------


@pytest.mark.parametrize("name", [*HOSTILE_TITLES, "ordinary.mp4", "a" * 300])
def test_sanitizing_is_idempotent(name: str) -> None:
    """An acceptance criterion, and the property that lets a path be passed through twice.

    `T-012` sanitizes for the `REQ-011` preview and again before writing; if the second pass
    changed the result, the preview would be a lie.
    """
    once = sanitize_component(name)
    assert sanitize_component(once) == once


@pytest.mark.parametrize("candidate", [*ESCAPE_ATTEMPTS, "Channel/Video.mp4"])
def test_safe_output_path_is_idempotent(output_dir: Path, candidate: str) -> None:
    first = safe_output_path(output_dir, candidate)
    second = safe_output_path(output_dir, str(first.relative_to(output_dir)))
    assert first == second


def test_sanitizing_is_deterministic() -> None:
    """No clock, no randomness, no `os.name` — identical input, identical output, either host."""
    hostile = 'CON.mp4 <with> "everything"...   '
    assert len({sanitize_component(hostile) for _ in range(50)}) == 1


@pytest.mark.parametrize(
    ("candidate", "expected_parts"),
    [
        ("Channel\\Video.mp4", ("Channel", "Video.mp4")),
        ("Channel/Video.mp4", ("Channel", "Video.mp4")),
        ("A\\B\\C.mp4", ("A", "B", "C.mp4")),
        ("A/B\\C.mp4", ("A", "B", "C.mp4")),
    ],
)
def test_both_platforms_separators_are_understood_on_either_host(
    output_dir: Path, candidate: str, expected_parts: tuple[str, ...]
) -> None:
    """§7 requires *both* platforms' rules on *both* platforms — including separators.

    Mutation testing caught this gap: restricting the split to the host's own separator left
    all 111 tests green. Containment still held, because a stray backslash is replaced by the
    illegal-character rule — but a Windows-style path was flattened into one mangled filename
    on Linux instead of being read as a path. Same input, different structure per host, which
    is exactly what `NFR-004` says must not happen.

    The previous version of this test compared `sanitize_component("aux.mp4")` with itself and
    proved nothing.
    """
    result = safe_output_path(output_dir, candidate)
    assert result.relative_to(output_dir).parts == expected_parts
    assert is_contained(result, output_dir)


def test_a_windows_style_traversal_is_split_and_dropped_on_either_host(output_dir: Path) -> None:
    """The security half of the same gap: `..` must be *removed*, not mangled into a name."""
    result = safe_output_path(output_dir, "..\\..\\evil.mp4")
    assert result.relative_to(output_dir).parts == ("evil.mp4",)
    assert is_contained(result, output_dir)


# --- length -----------------------------------------------------------------------------------


def test_a_long_name_is_shortened_but_keeps_its_extension() -> None:
    """Truncation that eats the extension changes what the file *is* to every tool."""
    result = sanitize_filename("a" * 500 + ".mp4")
    assert result.endswith(".mp4")
    assert len(result.encode("utf-8")) <= MAX_COMPONENT_BYTES


def test_length_is_budgeted_in_bytes_not_characters() -> None:
    """A component of 255 astral-plane characters is 1020 bytes and fails on ext4.

    Emoji titles are ordinary, so a naive character count would be wrong in production rather
    than in theory.
    """
    result = sanitize_component("🎵" * 200 + ".mp4")
    assert len(result.encode("utf-8")) <= MAX_COMPONENT_BYTES


def test_shortening_never_splits_a_character() -> None:
    """Truncating UTF-8 mid-sequence yields an undecodable name."""
    result = sanitize_component("🎵" * 200)
    result.encode("utf-8").decode("utf-8")  # raises if a surrogate survived


def test_an_over_long_assembled_path_is_shortened(tmp_path: Path) -> None:
    """A long name inside a deep directory is shortened to fit, keeping its extension.

    The directory is sized **from the remaining budget** rather than hard-coded. An earlier
    version used a fixed 80+80 depth, which left room under Linux's short `tmp_path` and none
    under the Windows runner's much longer one (a `Users/runneradmin/AppData/Local/Temp/...`
    prefix) — so the module correctly raised and the test failed on Windows only. The defect was
    the test's platform assumption, not the module's behavior. CI caught it, which is what the
    two-platform matrix is for.
    """
    room_for_filename = 50
    padding = MAX_PATH_CHARACTERS - len(str(tmp_path)) - 1 - room_for_filename
    if padding < 1:
        pytest.skip(f"tmp_path is already {len(str(tmp_path))} characters; no room to construct")

    deep = tmp_path / ("d" * min(padding, 100))
    deep.mkdir(parents=True)

    result = safe_output_path(deep, "f" * 300 + ".mp4")
    assert len(str(result)) <= MAX_PATH_CHARACTERS
    assert result.suffix == ".mp4"
    assert is_contained(result, deep)


def test_a_directory_leaving_no_room_for_a_filename_raises(tmp_path: Path) -> None:
    """Better a clear error than a zero-length filename or a silent write elsewhere."""
    # Sized past the budget from wherever tmp_path happens to start, so this holds on both
    # platforms rather than only where tmp_path is short.
    overshoot = MAX_PATH_CHARACTERS - len(str(tmp_path)) + 20
    long_dir = tmp_path / ("d" * min(max(overshoot, 1), 100))
    while len(str(long_dir)) < MAX_PATH_CHARACTERS:
        long_dir = long_dir / ("e" * 60)
    long_dir.mkdir(parents=True)
    with pytest.raises(UnsafePathError):
        safe_output_path(long_dir, "clip.mp4")


def test_shortening_two_similar_long_names_does_not_collide() -> None:
    """An acceptance criterion: shortening must not merge two distinct neighbours.

    Both are truncated to the same budget, so the distinguishing part must survive — here the
    difference is early enough in the stem to be kept.
    """
    first = sanitize_filename("Album A - " + "x" * 400 + ".mp4")
    second = sanitize_filename("Album B - " + "x" * 400 + ".mp4")
    assert first != second


# --- layering ---------------------------------------------------------------------------------


def test_paths_module_imports_no_qt_and_no_ytdlp() -> None:
    """Belt and braces alongside the layering test, since this module is `core/`."""
    source = (Path(__file__).parents[2] / "src/tracks_and_trails/core/paths.py").read_text()
    assert "PySide6" not in source
    assert "yt_dlp" not in source
