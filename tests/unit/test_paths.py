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
    DERIVED_COMPONENT_LENGTH,
    MAX_COMPONENT_BYTES,
    MAX_PATH_CHARACTERS,
    UnsafePathError,
    contained_output_path,
    derived_component,
    is_contained,
    numbered_variant,
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

#: Transcribed by hand from Microsoft's *Naming Files, Paths, and Namespaces*.
#:
#: **Not** imported from `core.paths` (`T010-R1`'s lesson, which this file relearned): deriving
#: the expectation from `_RESERVED_NAMES` made the test shrink whenever production did, so
#: removing the superscript digits left every test green.
MICROSOFT_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{d}" for d in "123456789\u00b9\u00b2\u00b3"}
    | {f"LPT{d}" for d in "123456789\u00b9\u00b2\u00b3"}
)

#: Names that merely *look* reserved and must pass through untouched.
#:
#: `COM0`/`LPT0` are here because a correction pass wrongly added them to production, which
#: mangled them into `COM0_`/`LPT0_` — colliding with the exact names a user might already have.
NOT_RESERVED_BY_MICROSOFT = ("COM0", "LPT0", "COM10", "LPT10", "COM", "LPT", "CONS", "NULL")


def test_production_matches_microsofts_reserved_set_exactly() -> None:
    """`T034-R4`. An **equality**, checked against the transcribed list.

    Both directions matter, and the second was learned the hard way. Missing a reserved name
    ships an unopenable file; *inventing* one mangles a legal filename and, worse, collides —
    `COM0` became `COM0_`, which is what a real `COM0_` also produces.
    """
    from tracks_and_trails.core.paths import _RESERVED_NAMES

    assert _RESERVED_NAMES == MICROSOFT_RESERVED_NAMES, (
        f"missing: {sorted(MICROSOFT_RESERVED_NAMES - _RESERVED_NAMES)}; "
        f"invented: {sorted(_RESERVED_NAMES - MICROSOFT_RESERVED_NAMES)}"
    )


@pytest.mark.parametrize("name", NOT_RESERVED_BY_MICROSOFT)
def test_names_that_only_look_reserved_pass_through_untouched(name: str) -> None:
    """Mangling a legal name is not a safe default — it creates the collision it avoids."""
    assert sanitize_component(name) == name
    assert sanitize_component(f"{name}.mp4") == f"{name}.mp4"


@pytest.mark.parametrize("reserved", ["COM1", "CON", "aux", "LPT\u00b9", "NUL"])
def test_defusing_a_reserved_name_does_not_collide_with_its_plausible_neighbour(
    reserved: str,
) -> None:
    """`T-045`. A defused name must not be one a user would realistically also hold.

    `COM1` and a legal file named `COM1_` both used to yield `COM1_`, so two distinct names
    landed on one path — the same collision class the truncation differentiator exists to
    prevent, reached by a different route. The bare `_` suffix is now a digest.
    """
    defused = sanitize_component(reserved)
    assert defused != reserved, f"{reserved!r} must be renamed at all"
    assert defused != sanitize_component(f"{reserved}_")
    assert sanitize_component(defused) == defused, "defusing must stay idempotent"


@pytest.mark.parametrize("reserved", ["COM1", "CON", "aux", "LPT¹", "NUL"])
def test_a_defused_name_is_a_fixed_point_and_shares_it_with_a_whole_class(
    reserved: str,
) -> None:
    """`T045-R1`, `T045-R3`, `DAT-002`. The residual collision, described honestly.

    No stateless idempotent sanitizer can promise a defused name collides with nothing: for
    reserved `x`, `y = sanitize_component(x)` is itself legal input, and idempotence forces
    `sanitize_component(y) == y == sanitize_component(x)`. The maintainer kept idempotence —
    `T-012` previews a path under `REQ-011` before writing it, and a preview disagreeing with the
    write would be a lie — and narrowed the promise instead (`DAT-002`).

    **This does not claim to enumerate the colliding inputs, and an earlier version wrongly did**
    (`T045-R3`). It checked six hand-picked candidates and called the result the exact set, while
    `defused + " "`, `defused + "."`, `"CON\\t"` and `"C\\x00ON"` all map to `defused` too —
    the test passed because nothing outside its own list was ever asked.

    Normalization is many-to-one by design: control-character stripping, trailing dot and space
    removal, and reserved-name defusing each merge inputs deliberately, and every merge widens
    this class. What is asserted below is what actually holds — the output is a fixed point, the
    plausible neighbour stays distinct, and the class is demonstrably wider than one might
    assume. A real uniqueness guarantee needs to know what is already on disk, and is `T-046`.
    """
    defused = sanitize_component(reserved)

    assert sanitize_component(defused) == defused, "the output must be a fixed point"
    assert sanitize_component(f"{reserved}_") != defused, "the plausible neighbour stays distinct"

    # Not an enumeration — a demonstration that the class is wider than the reserved name alone,
    # so nobody reads the fixed point above as "only these collide".
    for also_colliding in (f"{reserved} ", f"{reserved}.", f"{defused} ", f"{defused}.", defused):
        assert sanitize_component(also_colliding) == defused


@pytest.mark.parametrize("reserved", ["CON", "AUX", "NUL", "COM1", "LPT9", "\u0043\u004f\u004e"])
@pytest.mark.parametrize("decoration", ["", " ", "  ", ".", ". ", " .", "\t"])
def test_trailing_whitespace_cannot_smuggle_a_reserved_name_through(
    reserved: str, decoration: str
) -> None:
    """Found by verification, not by review: `"CON "` came out as `"CON"`, undefused.

    Windows discards trailing dots and spaces when creating a file, so `"CON "` *is* `CON` —
    an unopenable file. The reserved check ran on the unstripped stem, missed it, and the final
    strip then produced the bare reserved name anyway.

    Every decoration of every reserved form is checked, because the bug was invisible for the
    one spelling the suite happened to use.
    """
    from tracks_and_trails.core.paths import _RESERVED_NAMES

    result = sanitize_component(f"{reserved}{decoration}")
    bare = result.partition(".")[0].rstrip(". ").upper()
    assert bare not in _RESERVED_NAMES, f"{reserved + decoration!r} sanitized to {result!r}"


@pytest.mark.parametrize("decorated", ["CON ", "AUX  ", "COM1.", "CON .mp4", "NUL. "])
def test_decorated_reserved_names_are_idempotent(decorated: str) -> None:
    """The second half of the same defect.

    `sanitize("CON ")` returned `"CON"` while `sanitize("CON")` returned `"CON-<hex>"`, so two
    passes disagreed — and `T-012` sanitizes once for the `REQ-011` preview and again before
    writing, which would have made the preview a lie.
    """
    once = sanitize_component(decorated)
    assert sanitize_component(once) == once


def test_a_reserved_name_and_its_padded_form_produce_one_path() -> None:
    """`CON` and `CON ` are the same file on Windows, so collapsing them is correct.

    Recorded deliberately: this is the one place the module *merges* two inputs rather than
    keeping them distinct, and it is the conservative choice under the cross-platform rule.
    """
    assert sanitize_component("CON") == sanitize_component("CON ") == sanitize_component("CON.")


def test_a_defused_reserved_name_keeps_its_extension() -> None:
    """The rename must not cost the extension — the `T034-R3` property, at a different seam."""
    assert sanitize_component("CON.mp4").endswith(".mp4")
    assert sanitize_component("aux.mkv").endswith(".mkv")


def test_defusing_is_stable_across_calls() -> None:
    """A path that changed between the preview and the write would make the preview a lie."""
    assert len({sanitize_component("CON.mp4") for _ in range(20)}) == 1


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


def test_a_symlink_out_of_the_directory_is_not_contained(tmp_path: Path, symlinks: None) -> None:
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


def test_a_symlink_escape_is_rejected_through_the_public_entry_point(
    tmp_path: Path, symlinks: None
) -> None:
    """`T034-R1`. The security gate must be exercised through `safe_output_path`, not only
    through `is_contained`.

    Neutralising the candidate *string* says nothing about the *filesystem*. An existing symlink
    under the output directory pointing outside it makes the joined path resolve elsewhere, so
    the final containment check is genuinely reachable — contrary to what an earlier comment
    here claimed, and contrary to a mutation that only looked green because nothing drove a
    symlink through this entry point.
    """
    target = tmp_path / "Downloads"
    target.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (target / "link").symlink_to(outside)

    with pytest.raises(UnsafePathError):
        safe_output_path(target, "link/clip.mp4")


def test_a_symlink_inside_the_directory_is_still_allowed(tmp_path: Path, symlinks: None) -> None:
    """The rejection must be about *where it resolves*, not about symlinks as such."""
    target = tmp_path / "Downloads"
    (target / "real").mkdir(parents=True)
    (target / "link").symlink_to(target / "real")

    result = safe_output_path(target, "link/clip.mp4")
    assert is_contained(result, target)


def test_an_ordinary_subdirectory_is_allowed(output_dir: Path) -> None:
    """Containment must not be so strict that legitimate templates break.

    Output templates routinely produce `%(uploader)s/%(title)s.%(ext)s`.
    """
    result = safe_output_path(output_dir, "Some Channel/Some Video.mp4")
    assert is_contained(result, output_dir)
    assert result.parent.name == "Some Channel"
    assert result.name == "Some Video.mp4"


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("A: The Movie.mp4", "A_ The Movie.mp4"),
        ("E: Live at Wembley.mp4", "E_ Live at Wembley.mp4"),
        ("C:file.mp4", "C_file.mp4"),
        ("Artist: Song.mp4", "Artist_ Song.mp4"),
    ],
)
def test_a_title_beginning_with_a_letter_and_colon_is_sanitized_not_rejected(
    output_dir: Path, title: str, expected: str
) -> None:
    """Found by verification: `"A: The Movie.mp4"` was rejected outright.

    A single letter plus colon parses as a Windows drive, and discarding the whole component
    left nothing usable — so a legal title failed the download entirely. Only a component that
    *is* a drive specifier is dropped now; one that merely begins with one is sanitized like any
    other colon, which is what `"Artist: Song.mp4"` already got.
    """
    result = safe_output_path(output_dir, title)
    assert result.name == expected
    assert is_contained(result, output_dir)


def test_a_real_drive_prefixed_path_still_loses_its_drive(output_dir: Path) -> None:
    """The security half must not regress: an absolute Windows path stays contained."""
    for candidate in ("C:\\Windows\\evil.mp4", "C:/Windows/evil.mp4"):
        result = safe_output_path(output_dir, candidate)
        assert result.relative_to(output_dir).parts == ("Windows", "evil.mp4")
        assert is_contained(result, output_dir)


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
    "name",
    [
        "CON",
        "con",
        "CoN",
        "CON.mp4",
        "aux.mkv",
        "NUL.webm",
        "COM1.mp4",
        "LPT9.mp3",
        # `T034-R4`: Microsoft reserves these too, and all six passed through unchanged.
        "COM0",
        "LPT0.mp4",
        "COM\u00b9",
        "COM\u00b2",
        "COM\u00b3",
        "LPT\u00b9.mp4",
        "LPT\u00b2.mkv",
        "LPT\u00b3",
    ],
)
def test_reserved_device_names_are_defused_including_with_extensions(name: str) -> None:
    """`CON.mp4` is as unusable as `CON` on Windows — the case usually missed.

    The check must run on the stem, not the whole name.
    """
    result = sanitize_component(name)
    stem = result.partition(".")[0]
    assert stem.upper() not in MICROSOFT_RESERVED_NAMES, (
        f"{name!r} sanitized to {result!r}, whose stem is still a reserved device name"
    )


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


def test_shortening_raises_rather_than_dropping_the_extension() -> None:
    """`T034-R3`, exercised directly and deterministically.

    `_shorten_to` is private, but it encodes the rule the acceptance criterion states, and the
    filesystem-level version of this test cannot reliably construct a budget tight enough on
    every host — the first attempt took its `else` branch and passed against the bug.

    The earlier fallback returned `name[:limit]`, so a two-character budget turned `clip.mp4`
    into `cl`: an extensionless path every tool would misidentify, produced silently.
    """
    from tracks_and_trails.core.paths import _shorten_to

    with pytest.raises(UnsafePathError):
        _shorten_to("clip.mp4", 2)
    with pytest.raises(UnsafePathError):
        _shorten_to("clip.mp4", 5)


def test_shortening_keeps_the_extension_whenever_it_can() -> None:
    """The counterpart, so the rule above cannot be satisfied by always raising."""
    from tracks_and_trails.core.paths import _shorten_to

    result = _shorten_to("a" * 200 + ".mp4", 40)
    assert result.endswith(".mp4")
    assert len(result) <= 40


def test_a_directory_leaving_no_room_for_a_filename_raises(tmp_path: Path) -> None:
    """Better a clear error than a zero-length filename or a silent write elsewhere.

    **The directory is not created** (`T-067`). It used to be, and that `mkdir` was the only
    thing in this test that touched a filesystem — so on Windows with `LongPathsEnabled=0`,
    which is the *default*, the test died in its own setup with `WinError 206` before reaching
    a single assertion. It passed on CI only because GitHub's runner images set that value to
    `1`.

    Removing it costs nothing, because `safe_output_path` never consults the filesystem on this
    branch: the raise below fires at the length budget, several lines before the one call that
    resolves anything. A directory that exists and a directory that is merely named are the
    same input to the code under test.
    """
    # Sized past the budget from wherever tmp_path happens to start, so this holds on both
    # platforms rather than only where tmp_path is short.
    overshoot = MAX_PATH_CHARACTERS - len(str(tmp_path)) + 20
    long_dir = tmp_path / ("d" * min(max(overshoot, 1), 100))
    while len(str(long_dir)) < MAX_PATH_CHARACTERS:
        long_dir = long_dir / ("e" * 60)
    with pytest.raises(UnsafePathError):
        safe_output_path(long_dir, "clip.mp4")


def test_a_path_this_accepts_is_one_the_filesystem_will_actually_take(tmp_path: Path) -> None:
    """The budget has to stay inside what the OS will create, not merely inside itself (`T-067`).

    Every other length test here compares `safe_output_path`'s output against
    `MAX_PATH_CHARACTERS`, which is this project's own constant — so all of them would still
    pass if that constant were raised past what Windows accepts. This one writes the file.

    That is the question `T-067` is really about. Windows refuses a path beyond `MAX_PATH` (260)
    unless `LongPathsEnabled` is set, and its default is `0`; the runners set it to `1`, so a
    budget that had drifted too high would have been invisible on every CI run and immediate on
    an ordinary desktop.
    """
    path = safe_output_path(tmp_path, "x" * 400 + ".mp4")
    assert len(str(path)) <= MAX_PATH_CHARACTERS

    # The real assertion is that this line does not raise.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    assert path.is_file(), f"{path} passed the budget but the filesystem would not take it"


def test_shortening_two_names_differing_only_past_the_cut_does_not_collide() -> None:
    """`T034-R2`. The acceptance criterion, tested where it actually bites.

    The earlier version differed at character 7 — inside the retained prefix, where naive
    truncation already preserves the distinction — so it passed against an implementation that
    collided. These differ only in their **final** character, well beyond anything a prefix
    keeps, and two downloads fighting over one path is the failure it prevents.
    """
    first = sanitize_filename("x" * 400 + "A.mp4")
    second = sanitize_filename("x" * 400 + "B.mp4")
    assert first != second
    assert first.endswith(".mp4") and second.endswith(".mp4")


def test_the_differentiator_is_wide_enough_to_resist_collisions() -> None:
    """`T034-R2`, second round. A 32-bit digest collided at 96,718 candidates.

    Asserted as a property of the marker rather than by searching, because a search test would
    be slow and would only prove the bound it happened to reach. 64 bits puts the birthday
    bound around 2^32, far beyond any plausible directory.
    """
    from tracks_and_trails.core.paths import _MARKER_BYTES, _marker

    assert _MARKER_BYTES >= 8, "a 32-bit digest has a demonstrated collision at ~10^5 names"
    assert len(_marker("x")) == 1 + 2 * _MARKER_BYTES


def test_many_long_names_differing_only_past_the_cut_stay_distinct() -> None:
    """The behavioural counterpart, at a scale that would have caught the 4-byte digest."""
    names = {sanitize_filename("x" * 400 + str(i) + ".mp4") for i in range(20_000)}
    assert len(names) == 20_000


def test_the_differentiator_is_stable_across_calls_and_processes() -> None:
    """It must be a digest, not a counter or anything else with state.

    A path that changes between the `REQ-011` preview and the write would make the preview a
    lie, and one that differs between the GUI and worker processes would be worse.
    """
    name = "y" * 400 + ".mp4"
    assert len({sanitize_filename(name) for _ in range(20)}) == 1


def test_two_identical_long_names_still_produce_one_path() -> None:
    """The differentiator distinguishes *different* inputs; it must not split identical ones."""
    assert sanitize_filename("z" * 400 + ".mp4") == sanitize_filename("z" * 400 + ".mp4")


# --- layering ---------------------------------------------------------------------------------


def test_paths_module_imports_no_qt_and_no_ytdlp() -> None:
    """Belt and braces alongside the layering test, since this module is `core/`."""
    source = (Path(__file__).parents[2] / "src/tracks_and_trails/core/paths.py").read_text()
    assert "PySide6" not in source
    assert "yt_dlp" not in source


# --- T-046's naming half, which stays pure -----------------------------------------------------


def test_a_numbered_variant_reads_the_way_a_file_manager_writes_one() -> None:
    """` (2)` rather than a digest: a second copy of a video should be recognisable as one.

    `T-045`'s digest keeps *distinct* inputs apart, which is the opposite problem — here the two
    inputs really are the same name and the user needs to tell the files apart by eye.
    """
    assert numbered_variant(Path("/out/Clip.mp4"), 2) == Path("/out/Clip (2).mp4")
    assert numbered_variant(Path("/out/Clip.mp4"), 17) == Path("/out/Clip (17).mp4")


def test_a_numbered_variant_keeps_the_extension() -> None:
    """The extension is what every tool reading the file uses to decide what it is."""
    assert numbered_variant(Path("/out/A.Long.Name.mkv"), 3).name == "A.Long.Name (3).mkv"
    assert numbered_variant(Path("/out/no-extension"), 2).name == "no-extension (2)"


def test_numbering_is_pure_and_asks_nothing_of_the_filesystem(tmp_path: Path) -> None:
    """`DAT-002` moved "does this collide?" out of this module deliberately.

    A pure function of one string cannot answer a question about the filesystem, and pretending
    otherwise is what produced an unreachable criterion in the first place. So this must produce
    a name for a path that does not exist, and must not create one.
    """
    result = numbered_variant(tmp_path / "nothing-here.mp4", 2)

    assert result.name == "nothing-here (2).mp4"
    assert not result.exists()
    assert list(tmp_path.iterdir()) == []


def test_a_variant_below_two_is_a_programming_error() -> None:
    """`(1)` is not a thing a file manager writes, and `(0)` would collide with the original."""
    for index in (1, 0, -1):
        with pytest.raises(ValueError, match="starts at 2"):
            numbered_variant(Path("/out/Clip.mp4"), index)


def test_a_long_name_loses_stem_rather_than_its_number(tmp_path: Path) -> None:
    """**The marker survives; the stem is what gives way.**

    Trimming the marker to fit would produce two candidates with the same name, which is the one
    thing this function exists to prevent. The extension survives for `_shorten_to`'s reason.
    """
    long_name = tmp_path / (("x" * 400) + ".mp4")

    result = numbered_variant(long_name, 2)

    assert result.name.endswith(" (2).mp4"), f"the number was trimmed away: {result.name!r}"
    assert len(result.name.encode("utf-8")) <= MAX_COMPONENT_BYTES
    assert len(str(result)) <= MAX_PATH_CHARACTERS


def test_two_long_names_sharing_a_prefix_still_get_different_numbers(tmp_path: Path) -> None:
    """Shortening must not merge the candidates back together.

    `T034-R2` is the same failure one layer down: prefix truncation alone collides, so the
    truncation carries a digest of what it dropped. Numbering on top of that has to keep the
    numbers distinguishable even when both stems are cut to the same budget.
    """
    long_name = tmp_path / (("x" * 400) + ".mp4")

    assert numbered_variant(long_name, 2) != numbered_variant(long_name, 3)


def test_a_directory_with_no_room_left_is_refused_rather_than_silently_shortened(
    tmp_path: Path,
) -> None:
    """`_shorten_to`'s rule, and the same reasoning: failing is the honest outcome.

    Silently returning something that is not the requested extension writes a file every tool
    misidentifies, while the user was told the download succeeded.
    """
    deep = Path("/" + "d" * (MAX_PATH_CHARACTERS - 4)) / "Clip.mp4"

    with pytest.raises(UnsafePathError, match="no room"):
        numbered_variant(deep, 2)


def test_a_multibyte_name_is_cut_to_the_byte_budget_not_the_character_one() -> None:
    """The two budgets are **different units**, and a name can satisfy one while breaking the
    other.

    Measured: with the byte truncation removed, `test_a_long_name_loses_stem_rather_than_its_number`
    still passed. Its stem is ASCII in a deep `tmp_path`, so the *character* budget fired first
    and cut the name to something that happened to fit the byte budget too — the byte branch was
    never the thing under test.

    A hundred three-byte characters is 300 bytes in 100 characters: far over
    `MAX_COMPONENT_BYTES`, comfortably inside `MAX_PATH_CHARACTERS` under a short directory. Only
    the byte branch can save it.
    """
    path = Path("/o") / ("あ" * 100 + ".mp4")

    result = numbered_variant(path, 2)

    assert len(str(result)) <= MAX_PATH_CHARACTERS, "this case is meant to fit the path budget"
    assert len(result.name.encode("utf-8")) <= MAX_COMPONENT_BYTES, (
        f"{len(result.name.encode('utf-8'))} bytes, over the {MAX_COMPONENT_BYTES}-byte "
        "component budget: the character budget cannot stand in for it"
    )
    assert result.name.endswith(" (2).mp4")


# --- T-112: the one function a preview and a write both call (`REQ-011`) -----------------------
#
# `contained_output_path` was five lines inside `worker._validated_target`, where the parent
# process could not reach them — so `REQ-011`'s live preview would have had to restate the escape
# refusal and the containment call. `docs/UX_SPEC.md` §9.1 says in as many words that two would
# drift, and `T-046` is what drift here costs.


#: The rendered paths a **template** must be refused for, transcribed rather than filtered out of
#: `ESCAPE_ATTEMPTS`. That list is about what `safe_output_path` must *neutralize*, and the two
#: questions have different answers: `....//....//evil.mp4` names no `..` component at all, so it
#: never leaves the directory and is cleaned rather than rejected. Deriving one list from the other
#: would hide exactly that difference — `T010-R1`'s lesson, which this file has already relearned
#: once.
TEMPLATE_ESCAPES = [
    "../evil.mp4",
    "../../../../etc/passwd",
    "..\\..\\windows\\system32\\evil.mp4",
    "/etc/passwd",
    "C:\\Windows\\System32\\evil.mp4",
    "C:/Windows/evil.mp4",
    "\\\\server\\share\\evil.mp4",
    "//server/share/evil.mp4",
    "subdir/../../escape.mp4",
    "clip/../../../evil.mp4",
]


@pytest.mark.parametrize("rendered", TEMPLATE_ESCAPES)
def test_a_template_that_escapes_the_directory_is_refused_not_redirected(
    tmp_path: Path, rendered: str
) -> None:
    """`T-012`'s criterion: a template rendering outside the target directory is **rejected**.

    The distinction from `safe_output_path` is the whole reason this function exists. A *title*
    that escapes is neutralized, because a video called `../../etc/passwd` should still download.
    A *template* that escapes is the user's own instruction, and quietly rewriting it into the
    chosen folder tells them it worked when it did not.
    """
    with pytest.raises(UnsafePathError, match="outside the chosen directory"):
        contained_output_path(tmp_path, rendered)

    # The neutralizing path is still available and still neutralizes, so the two have not merged.
    assert is_contained(safe_output_path(tmp_path, rendered), tmp_path)


def test_a_decoy_that_never_actually_leaves_is_cleaned_rather_than_refused(
    tmp_path: Path,
) -> None:
    """`....//....//evil.mp4` looks like traversal and is not: no component of it is `..`.

    Refusing it would mean refusing a legal, if odd, filename on the strength of how it looks —
    and the refusal a user is shown has to be about what would actually have happened.
    """
    result = contained_output_path(tmp_path, "....//....//evil.mp4")

    assert is_contained(result, tmp_path)
    assert result.name == "evil.mp4"


def test_a_template_resolving_to_an_absolute_path_is_refused(tmp_path: Path) -> None:
    """Not only a literal `..`: a rendered field can produce a root or a drive on its own.

    Both spellings, on both platforms, because `_components` reads either separator whatever the
    host is — a Windows escape must not survive being judged by POSIX rules.
    """
    for rendered in (
        "/etc/cron.d/payload.mp4",
        "C:\\Windows\\System32\\evil.mp4",
        "//host/share/x",
    ):
        with pytest.raises(UnsafePathError):
            contained_output_path(tmp_path, rendered)


def test_a_subdirectory_inside_the_directory_is_kept(tmp_path: Path) -> None:
    """`REQ-011` is *path and filename* control, so a template may make folders — and only inside.

    Asserted alongside the refusals rather than apart from them: a containment check that refused
    everything would pass every test above and make the feature useless.
    """
    result = contained_output_path(tmp_path, "Some Artist/Some Album/Track.mp3")

    assert result == tmp_path / "Some Artist" / "Some Album" / "Track.mp3"
    assert is_contained(result, tmp_path)


def test_the_title_inside_a_contained_template_is_still_sanitized(tmp_path: Path) -> None:
    """The two treatments meet here, and the sanitizing half must not be lost.

    A rendered name carrying characters NTFS forbids is cleaned rather than refused: the template
    is the user's and the title is not.
    """
    result = contained_output_path(tmp_path, 'A<title>with"illegal|characters?.mp4')

    assert is_contained(result, tmp_path)
    assert not set(result.name) & set('<>:"/\\|?*'), result.name


# --- T113-R1: a derived component, because a job id is not a filename --------------------------


@pytest.mark.parametrize(
    "key",
    [
        "../../../../outside",
        "../outside",
        "..\\..\\outside",
        "/etc/passwd",
        "C:\\Windows\\System32",
        "//server/share",
        "....//....//outside",
        ".",
        "..",
        "CON",
        "a" * 500,
        "🎬 emoji",
        "",
    ],
)
def test_a_derived_component_is_always_one_safe_component(key: str) -> None:
    """**`T113-R1`, Critical.** A job id is validated as non-empty text and joined into a path.

    Traversal is not defended against here — it is unrepresentable. The output is `[0-9a-f]{32}`
    whatever the input, so there is no separator, no `..`, no drive letter and no reserved name to
    reason about, on either platform.
    """
    component = derived_component(key)

    assert len(component) == DERIVED_COMPONENT_LENGTH
    assert set(component) <= set("0123456789abcdef"), component
    assert Path(component).name == component, "the derived name is not a single component"


def test_a_derived_component_is_stable_and_distinct() -> None:
    """Stable, so a worker and the parent agree and a later run finds what an earlier one left
    (`REQ-017`); distinct, so two jobs never share a private directory (`T-046`'s whole subject)."""
    assert derived_component("job-1") == derived_component("job-1")
    assert derived_component("job-1") != derived_component("job-2")


@pytest.mark.parametrize("key", ["../../../../outside", "/etc", "C:\\Windows", "..\\..\\outside"])
def test_a_crafted_key_cannot_name_anything_outside_the_directory(tmp_path: Path, key: str) -> None:
    """The property the Critical is about, asserted on the joined path rather than on the name.

    `Path("/downloads") / ".staging-../../../../outside"` is a real directory outside the download
    folder — and the code that joins it then creates it with `parents=True` and removes it with
    `shutil.rmtree`.
    """
    inside = tmp_path / "downloads" / "nested"
    inside.mkdir(parents=True)

    joined = inside / f"prefix-{derived_component(key)}"

    assert is_contained(joined, inside)
    assert is_contained(joined, tmp_path)
