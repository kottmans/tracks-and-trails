"""`core/settings.py` — the bounds `REQ-013` states and the failures a hand-edited file can hold.

`ARC-007` puts the concurrency limit in `settings.toml` and puts the *bound* here rather than on
the control that edits it. `T-078`'s criteria say why: a spinbox clamping its own input bounds the
widget, and the file is hand-editable by design, so `concurrency = 0` must not reach the pool.

No Qt and no network, per `tests/` layout. This module is `core/`.
"""

import json
import os
from pathlib import Path

import pytest

from tracks_and_trails.core import presets as preset_registry
from tracks_and_trails.core.models import AudioCodec, MediaKind, Preset
from tracks_and_trails.core.settings import (
    CONCURRENCY_DEFAULT,
    CONCURRENCY_MAXIMUM,
    CONCURRENCY_MINIMUM,
    THEME_DEFAULT,
    THEME_NAMES,
    Settings,
    add_preset,
    all_presets,
    default_preset_of,
    duplicate_preset,
    free_preset_name,
    load,
    preset_named,
    remove_preset,
    save,
    set_default_preset,
    settings_path,
    update_preset,
    with_concurrency,
    with_download_directory,
    with_theme,
)


def write(path: Path, body: str) -> Path:
    target = path / "settings.toml"
    target.write_text(body, encoding="utf-8")
    return target


def toml_path(value: Path) -> str:
    """`value` as a TOML basic string, escaped. **Not optional, and Windows is why.**

    A test writing `directory = "{path}"` by interpolation produces `directory =
    "C:\\Users\\..."` — unescaped backslashes, which `tomllib` refuses with *Unescaped '\\' in
    a string*. The whole file is then a decode error, so every test doing it asserted the wrong
    branch on Windows and passed on Linux. That is `T146-R3`'s defect class, and CI caught four
    more instances of it after `T-146` was approved.

    `json.dumps` rather than a hand-rolled escaper: TOML basic strings share JSON's escapes for
    the characters a path can hold, and the production writer's own `_toml_string` is private to
    the module under test — a test should not reach into it to build the input it feeds back.
    """
    return json.dumps(str(value))


# --- what REQ-013 states ------------------------------------------------------------------


def test_the_defaults_are_the_ones_req_013_names() -> None:
    """Read from the module rather than restated, so a changed default fails here first.

    The maximum is asserted alongside them even though `REQ-013` does not name it: `ARC-007` chose
    16 deliberately, and a number changed by accident should fail somewhere.
    """
    assert (CONCURRENCY_DEFAULT, CONCURRENCY_MINIMUM) == (3, 1)
    assert CONCURRENCY_MAXIMUM == 16
    assert Settings().concurrency == 3


def test_settings_refuses_a_limit_below_the_minimum_in_code() -> None:
    """A caller passing 0 is a programming error; a *file* saying 0 is not (see `load`)."""
    with pytest.raises(ValueError, match="minimum is 1"):
        Settings(concurrency=0)
    with pytest.raises(ValueError, match="minimum is 1"):
        Settings(concurrency=-4)


def test_settings_refuses_a_limit_above_the_ceiling_in_code() -> None:
    """A caller asking for 40 has a bug; a *file* asking for it is clamped (see below).

    The asymmetry is the same one the minimum has, and for the same reason: code is written once
    and reviewed, a config file is typed by hand at midnight.
    """
    with pytest.raises(ValueError, match="ceiling is 16"):
        Settings(concurrency=CONCURRENCY_MAXIMUM + 1)
    with pytest.raises(ValueError, match="ceiling is 16"):
        Settings(concurrency=10_000)


def test_settings_accepts_the_boundaries_themselves() -> None:
    """Off-by-one in either direction would make one legitimate value unreachable."""
    assert Settings(concurrency=CONCURRENCY_MINIMUM).concurrency == 1
    assert Settings(concurrency=CONCURRENCY_MAXIMUM).concurrency == 16


def test_settings_refuses_a_non_integer_limit_in_code() -> None:
    with pytest.raises(TypeError, match="must be an int"):
        Settings(concurrency="3")  # type: ignore[arg-type]


def test_settings_refuses_a_boolean_because_bool_is_an_int() -> None:
    """`True` would otherwise pass every `isinstance(x, int)` check and mean a pool of one.

    **No `type: ignore` here, and its absence is the point.** `bool` is a subclass of `int`, so
    `Settings(concurrency=True)` type-checks cleanly — mypy has no complaint to suppress. The static
    gate cannot see this one, which is exactly why the runtime check exists.
    """
    with pytest.raises(TypeError, match="must be an int"):
        Settings(concurrency=True)


# --- the file: T-078's "absent or unparseable is stated, not discovered" -------------------


def test_an_absent_file_yields_the_defaults(tmp_path: Path) -> None:
    """The normal first run. Nothing exists yet and the application still starts."""
    assert load(tmp_path / "nothing-here.toml").settings == Settings()


def test_a_directory_where_the_file_should_be_yields_the_defaults(tmp_path: Path) -> None:
    """`OSError` rather than a parse failure, and the same answer. A real state after a bad copy."""
    (tmp_path / "settings.toml").mkdir()
    assert load(tmp_path / "settings.toml").settings == Settings()


@pytest.mark.parametrize(
    ("name", "body"),
    [
        ("truncated mid-write", "[queue]\nconcurrency = "),
        ("not toml at all", "<<<not toml>>>"),
        ("empty", ""),
        ("table missing", "[other]\nthing = 1\n"),
        ("key at the top level instead of in the table", "concurrency = 8\n"),
        ("table is a scalar", 'queue = "nope"\n'),
        ("key absent from a present table", "[queue]\nsomething_else = 1\n"),
    ],
)
def test_an_unusable_file_yields_the_defaults(name: str, body: str, tmp_path: Path) -> None:
    """Every shape a hand-edit or a partial write can leave, answered the same way.

    Parametrised rather than written as one test with several files, so a regression names the shape
    it broke on.
    """
    assert load(write(tmp_path, body)).settings == Settings(), (
        f"{name} did not fall back to defaults"
    )


def test_a_valid_file_is_used_as_written(tmp_path: Path) -> None:
    assert load(write(tmp_path, "[queue]\nconcurrency = 7\n")).settings.concurrency == 7


# --- the bound, applied to the file rather than to the widget ------------------------------


@pytest.mark.parametrize("written", [0, -1, -1000])
def test_a_file_below_the_minimum_is_raised_to_it_not_replaced_by_the_default(
    written: int, tmp_path: Path
) -> None:
    """`T-078`: a hand-edited `0` must not produce a pool that starts nothing.

    **Raised to the minimum, not replaced by the default**, and the distinction is the point: the
    user wrote a number whose evident intent is "as few as possible". Falling back to 3 would
    discard an edit that was legible.
    """
    limit = load(write(tmp_path, f"[queue]\nconcurrency = {written}\n")).settings.concurrency
    assert limit == CONCURRENCY_MINIMUM
    assert limit != CONCURRENCY_DEFAULT, (
        "a value below the minimum was replaced by the default, discarding a legible intent"
    )


@pytest.mark.parametrize("written", [17, 30, 300, 10_000, 10**9])
def test_a_file_above_the_ceiling_is_lowered_to_it_not_replaced_by_the_default(
    written: int, tmp_path: Path
) -> None:
    """`ARC-007`: the ceiling exists to catch a typo, so it must survive the typo it catches.

    **Lowered, not replaced by the default**, by the same reasoning as the floor read the other way:
    `30` says "a lot", and the most of "a lot" this application will do is 16. Falling back to 3
    would discard a legible intent.

    The values here are the realistic typo class — an extra zero, or a digit doubled — rather than
    abstract extremes. `10**9` is there because nothing should special-case magnitude.
    """
    limit = load(write(tmp_path, f"[queue]\nconcurrency = {written}\n")).settings.concurrency
    assert limit == CONCURRENCY_MAXIMUM
    assert limit != CONCURRENCY_DEFAULT, "a value above the ceiling fell back to the default"


def test_the_boundaries_themselves_survive_a_round_trip(tmp_path: Path) -> None:
    """Neither bound may be off by one; each is a value a user can legitimately choose."""
    assert load(write(tmp_path, "[queue]\nconcurrency = 1\n")).settings.concurrency == 1
    assert load(write(tmp_path, "[queue]\nconcurrency = 16\n")).settings.concurrency == 16


@pytest.mark.parametrize(
    ("name", "literal"),
    [
        ("a string", '"three"'),
        ("a decimal", "2.5"),
        ("a whole-looking float", "3.0"),
        ("true", "true"),
        ("false", "false"),
        ("an array", "[1, 2]"),
        ("an inline table", "{ n = 2 }"),
    ],
)
def test_a_file_whose_value_is_not_an_integer_yields_the_default(
    name: str, literal: str, tmp_path: Path
) -> None:
    """No intent to honour, so the default applies rather than a guess.

    `true` and `false` are here because `bool` is an `int` subclass: without an explicit check,
    `concurrency = true` would mean a pool of one and `false` would mean zero.
    """
    got = load(write(tmp_path, f"[queue]\nconcurrency = {literal}\n")).settings.concurrency
    assert got == CONCURRENCY_DEFAULT, f"{name} produced {got}"


# --- round trip and the write path ---------------------------------------------------------


def test_saved_settings_load_back_identically(tmp_path: Path) -> None:
    """Whole-object comparison, so a field added later that `save` forgets fails here."""
    target = tmp_path / "settings.toml"
    original = Settings(concurrency=5)
    save(original, target)
    assert load(target).settings == original


def test_saving_creates_the_directory_it_needs(tmp_path: Path) -> None:
    """First run writes into a config directory that does not exist yet."""
    target = tmp_path / "nested" / "deeper" / "settings.toml"
    save(Settings(concurrency=2), target)
    assert load(target).settings.concurrency == 2


def test_the_written_file_is_legible_to_the_person_who_opens_it(tmp_path: Path) -> None:
    """`DAT-001` chose TOML so a human can read it, and until Phase 4 that is how it is edited."""
    target = tmp_path / "settings.toml"
    save(Settings(concurrency=4), target)
    body = target.read_text(encoding="utf-8")
    assert body.startswith("#"), "no comment header for whoever opens this"
    assert "Safe to delete" in body
    assert f"Minimum {CONCURRENCY_MINIMUM}" in body
    assert f"maximum {CONCURRENCY_MAXIMUM}" in body
    assert f"default {CONCURRENCY_DEFAULT}" in body
    assert "separate worker process" in body, (
        "the header should say why a bigger number is not simply faster; it is the only place a "
        "hand-editor is told what the number costs"
    )


def test_saving_over_an_unwritable_path_does_not_raise(tmp_path: Path) -> None:
    """A read-only config directory is a real deployment state, not a hypothetical one.

    The same rule `save_geometry` follows: failing to persist a preference must not turn a clean
    exit into a crash on the way out.
    """
    blocked = tmp_path / "settings.toml"
    blocked.mkdir()  # a directory cannot be written as a file
    save(Settings(concurrency=6), blocked)  # must not raise


# --- with_concurrency ----------------------------------------------------------------------


def test_with_concurrency_applies_the_same_bounds_the_file_gets(tmp_path: Path) -> None:
    """A control handing over 0 gets the minimum and 40 gets the maximum — `load`'s answers.

    The bounds belong wherever the value changes, not only where it is read (`ARC-007`). A spinbox
    that clamps its own range bounds the widget; this bounds the value.
    """
    assert with_concurrency(Settings(), 0).concurrency == CONCURRENCY_MINIMUM
    assert with_concurrency(Settings(), -9).concurrency == CONCURRENCY_MINIMUM
    assert with_concurrency(Settings(), 40).concurrency == CONCURRENCY_MAXIMUM
    assert with_concurrency(Settings(), 6).concurrency == 6


def test_with_concurrency_leaves_the_original_alone() -> None:
    """`Settings` is frozen; this returns a copy, and a caller holding the old one is unaffected."""
    original = Settings(concurrency=3)
    assert with_concurrency(original, 9).concurrency == 9
    assert original.concurrency == 3


# --- the location ARCHITECTURE.md section 5 specifies --------------------------------------


def test_the_settings_file_is_where_section_5_says(tmp_path: Path) -> None:
    """And **not** doubled: `appauthor=False` is load-bearing on Windows.

    The same assertion `test_the_default_user_directory_is_not_doubled` makes for the yt-dlp
    directory, for the same platformdirs reason.
    """
    path = settings_path()
    assert path.name == "settings.toml"
    assert path.parent.name == "tracksandtrails"
    assert path.parent.parent.name != "tracksandtrails", "platformdirs inserted an author segment"
    assert Path(__file__).parent not in path.parents


# --- T-102 / ARC-008: a file that exists and cannot be used says so ------------------------
#
# Every row of `ARC-008`'s table, in **both** directions. The silent rows are the ones that
# matter: a missing file and a file that omits the value are the two an over-eager implementation
# reports, and they are the normal first run and an edit `save()`'s own header invites.


def test_a_missing_file_is_the_normal_first_run_and_reports_nothing(tmp_path: Path) -> None:
    """The single most common case. A first launch must not open with a warning."""
    answer = load(tmp_path / "nothing-here.toml")
    assert answer.settings == Settings()
    assert answer.problem is None


def test_a_file_that_omits_the_value_reports_nothing(tmp_path: Path) -> None:
    """`save()` writes "Safe to delete: every value falls back to its default." — so it must be.

    Three shapes of the same promise: an empty file, one with no `[queue]` table, and one whose
    `[queue]` table simply has no `concurrency` line. A user who took the header at its word and
    deleted the line must not then be told their file is broken.
    """
    for name, body in (
        ("empty", ""),
        ("no table", "# just a comment\n"),
        ("table without the key", "[queue]\n"),
        ("a different table", "[network]\nproxy = 'http://localhost'\n"),
    ):
        answer = load(write(tmp_path, body))
        assert answer.settings == Settings(), name
        assert answer.problem is None, f"{name} was reported, and ARC-008 keeps it silent"


def test_a_clamped_value_reports_nothing(tmp_path: Path) -> None:
    """Clamping honours the intent rather than discarding it, so nothing was lost to report.

    `ARC-008` names this as the edge it deliberately leaves silent, and as a reopening condition.
    Asserted so that if the decision changes, this test is what says so.
    """
    for written in ("0", "-5", "30", "1000"):
        answer = load(write(tmp_path, f"[queue]\nconcurrency = {written}\n"))
        assert answer.problem is None, (
            f"{written} was reported; ARC-008 clamps and stays silent because the user's evident "
            "intent is honoured up to the bound rather than discarded"
        )


def test_a_malformed_file_is_reported_with_the_parser_s_own_words(tmp_path: Path) -> None:
    """The line and column are the whole value of reporting, so they must survive."""
    target = write(tmp_path, "[queue]\nconcurrency = = 3\n")

    answer = load(target)

    assert answer.settings == Settings(), "the fallback itself must not change"
    assert answer.problem is not None, "an unparseable file was silently replaced by defaults"
    assert answer.problem.path == target
    assert any(ch.isdigit() for ch in answer.problem.reason), (
        f"reason {answer.problem.reason!r} carries no position; tomllib reports a line and column "
        "and discarding them leaves the reader no better off than the silence this replaces"
    )


def test_a_non_utf8_settings_file_is_reported_instead_of_aborting_startup(tmp_path: Path) -> None:
    """Invalid bytes are another way an existing TOML file cannot be parsed.

    ``tomllib.load`` raises ``UnicodeDecodeError`` before its TOML parser can turn the failure into
    ``TOMLDecodeError``.  The public contract is broader: ``load`` never raises for a file on disk.
    """
    target = tmp_path / "settings.toml"
    target.write_bytes(b"[queue]\nconcurrency = \xff\n")

    answer = load(target)

    assert answer.settings == Settings()
    assert answer.problem is not None
    assert answer.problem.path == target


def test_a_wrong_shaped_queue_section_is_reported(tmp_path: Path) -> None:
    """`ARC-008`: a file that parses but is not the shape this module writes discarded something.

    `queue` present as a *value* rather than a section is a hand-edit that went wrong — the user
    wrote something about the queue and none of it could be used. Distinct from the file simply not
    mentioning `[queue]`, which is covered above and stays silent.

    *(An earlier version of this test asserted that a top-level `queue = 'three'` was silent, on
    the strength of a comment left over from the pre-`ARC-008` code — "a file holding the key at the
    top level is not a partial success. Nothing in it is trusted." That reasoning is why nothing is
    *used*; it says nothing about whether the user is told. The decision's table settles it: not a
    table means reported.)*
    """
    for body in ("queue = 'three'\n", "queue = 5\n", "queue = [1, 2]\n"):
        answer = load(write(tmp_path, body))
        assert answer.settings == Settings(), body
        assert answer.problem is not None, f"{body!r}: a [queue] that is not a section was silent"
        assert "section" in answer.problem.reason

    assert load(write(tmp_path, "[queue]\nconcurrency = 3\n")).problem is None


def test_a_non_integer_value_is_reported_rather_than_quietly_defaulted(tmp_path: Path) -> None:
    """`"three"` and `2.5` do not say how many processes to run, so the value was discarded."""
    for literal in ('"three"', "2.5", "true", "[1, 2]", "{ n = 2 }"):
        answer = load(write(tmp_path, f"[queue]\nconcurrency = {literal}\n"))
        assert answer.settings.concurrency == CONCURRENCY_DEFAULT, literal
        assert answer.problem is not None, (
            f"{literal} was discarded silently — the user wrote something and got 3 with no reason"
        )
        assert "concurrency" in answer.problem.reason


def test_an_unreadable_file_is_told_apart_from_a_missing_one(tmp_path: Path) -> None:
    """The two most different cases this function has, and they used to share a branch.

    A directory where the file should be produces `IsADirectoryError` — an `OSError` that is not
    `FileNotFoundError`, which is exactly the distinction under test without needing to chmod
    anything (root ignores permission bits, so a permissions test would be a false negative in a
    container).
    """
    target = tmp_path / "settings.toml"
    target.mkdir()

    answer = load(target)

    assert answer.settings == Settings()
    assert answer.problem is not None, "a file that exists and cannot be opened was silent"
    assert answer.problem.path == target


def test_load_still_never_raises_for_any_of_them(tmp_path: Path) -> None:
    """The property that makes a broken config file a non-fatal state (`ARC-008`).

    **The non-UTF-8 row is `T102-R1`.** `tomllib.load` decodes bytes before parsing, so a file in
    another encoding raised `UnicodeDecodeError` — neither an `OSError` nor a `TOMLDecodeError`,
    so it escaped both branches and aborted composition. This matrix had no encoding case at all,
    which is why nothing caught it.
    """
    directory = tmp_path / "as-a-directory.toml"
    directory.mkdir()
    latin1 = tmp_path / "latin1.toml"
    latin1.write_bytes(b"[queue]\n# caf\xe9\nconcurrency = 3\n")
    truncated = tmp_path / "truncated.toml"
    truncated.write_bytes(b"[queue]\nconcurrency = 3  # \xf0\x9f")
    for target in (
        tmp_path / "absent.toml",
        write(tmp_path, "concurrency = = ="),
        write(tmp_path, "[queue]\nconcurrency = 'x'\n"),
        directory,
        latin1,
        truncated,
    ):
        load(target)


def test_a_file_in_another_encoding_is_reported_with_its_codec_and_offset(tmp_path: Path) -> None:
    """`T102-R1`: a decoding failure is another way an existing file cannot be used.

    The reason keeps the codec's own words and the byte offset, for the same reason the TOML branch
    keeps line and column: they are what tells somebody which editor wrote the file and where to
    look. A bare "could not be read" leaves them no better off than the silence this replaced.
    """
    target = tmp_path / "settings.toml"
    target.write_bytes(b"[queue]\nconcurrency = 3\n# caf\xe9\n")

    answer = load(target)

    assert answer.settings == Settings(), "the fallback itself must not change"
    assert answer.problem is not None, "a file in another encoding was silently replaced"
    assert answer.problem.path == target
    assert "UTF-8" in answer.problem.reason
    # **The offset, precisely** — not "contains a digit", which "UTF-8" satisfies by itself. A
    # mutation replacing the whole reason with "The file is not valid UTF-8." survived that
    # weaker assertion.
    try:
        target.read_bytes().decode("utf-8")
    except UnicodeDecodeError as expected:
        offset = expected.start
    else:  # pragma: no cover - the fixture above is deliberately undecodable
        raise AssertionError("the fixture decoded cleanly, so this test proves nothing")
    assert f"byte {offset}" in answer.problem.reason, (
        f"reason {answer.problem.reason!r} does not say where the bad byte is; that offset is "
        "what tells somebody which line their editor mangled"
    )


def test_the_summary_names_the_file_and_the_reason(tmp_path: Path) -> None:
    """The words a user reads, asserted with no display attached — which is why core owns them."""
    target = write(tmp_path, "[queue]\nconcurrency = = 3\n")
    problem = load(target).problem
    assert problem is not None

    summary = problem.summary

    assert str(target) in summary, "the summary does not name the file it is about"
    assert problem.reason in summary, "the summary drops the underlying reason"
    assert "default settings are in use" in summary
    assert "overwrite" in summary, (
        "the summary does not warn that saving settings replaces the file the user hand-edited"
    )


# --- T109-R5: the creation seam P-4's Save as preset… writes through ---------------------------
#
# `T-111` owns edit, duplicate, delete and set-default. This is create, and it exists now because
# `P-4` requires the options editor to offer the action — a control with nowhere to save to is one
# `UX-005` §5 forbids drawing. `T-111`'s own entry records that presets live in this file.


def a_preset(name: str = "Weekend viewing", **overrides: object) -> Preset:
    fields: dict[str, object] = {
        "name": name,
        "media_kind": MediaKind.VIDEO,
        "format_selector": "bestvideo+bestaudio/best",
        "output_template": "%(title)s.%(ext)s",
    }
    return Preset(**{**fields, **overrides})  # type: ignore[arg-type]


def test_a_saved_preset_survives_the_round_trip_whole(tmp_path: Path) -> None:
    """**Every field, compared as a whole object.**

    A per-field assertion goes green when a field stops being written; comparing the objects is
    what makes a `Preset` widening — which `ARC-010` has already done once — fail here rather than
    silently drop on the next save.
    """
    target = tmp_path / "settings.toml"
    preset = a_preset(
        media_kind=MediaKind.AUDIO,
        format_selector="bestaudio/best",
        audio_codec=AudioCodec.MP3,
        audio_quality="320",
        subtitle_languages=("en", "de"),
        embed_subtitles=True,
        remux_container="m4a",
        embed_metadata=True,
    )

    save(add_preset(Settings(concurrency=5), preset), target)
    read = load(target)

    assert read.problem is None, read.problem
    assert read.settings.presets == (preset,)
    assert read.settings.concurrency == 5, "the presets displaced the setting beside them"


def test_a_name_carrying_quotes_or_backslashes_survives(tmp_path: Path) -> None:
    """A preset name is user text, so the escaping is not optional.

    Hand-written TOML with no escaping produces a file this module cannot read back — the round
    trip breaking itself, silently, on a name somebody was entitled to type.
    """
    target = tmp_path / "settings.toml"
    preset = a_preset(name='My "best" \\ pick')

    save(add_preset(Settings(), preset), target)

    assert load(target).settings.presets == (preset,)


def test_a_colliding_name_is_refused_rather_than_disambiguated() -> None:
    """`REQ-009`: the name names the download, and `T-159` makes surfaces compare by it.

    Two presets sharing one would make a row's choice ambiguous to the code as well as to the
    reader. Refused loudly, because the caller is an editor with the user in front of it — picking
    a name for them is how *Audio only (MP3) (2)* appears in a list nobody meant to create.
    """
    settings = add_preset(Settings(), a_preset())

    with pytest.raises(ValueError, match="already exists"):
        add_preset(settings, a_preset())


def test_a_name_that_shadows_a_built_in_is_refused() -> None:
    """A saved *Audio only (MP3)* would shadow the one that ships, which is the worse collision."""
    with pytest.raises(ValueError, match="already exists"):
        add_preset(Settings(), a_preset(name=preset_registry.AUDIO_MP3.name))


def test_a_built_in_cannot_be_saved_as_the_users_own() -> None:
    """Everything in this file is the user's, and a stored `built_in` would claim otherwise."""
    with pytest.raises(ValueError, match="not the user's to save"):
        add_preset(Settings(), preset_registry.AUDIO_MP3)


def test_a_preset_read_back_is_never_built_in(tmp_path: Path) -> None:
    """A hand-edited `built_in = true` must not let a saved preset claim to ship with the app.

    Asserted through the file rather than through the constructor, because the file is the
    surface a user can actually edit.
    """
    target = tmp_path / "settings.toml"
    target.write_text(
        '[[preset]]\nname = "Sneaky"\nmedia_kind = "video"\n'
        'format_selector = "best"\noutput_template = "%(title)s.%(ext)s"\nbuilt_in = true\n',
        encoding="utf-8",
    )

    read = load(target)

    assert read.settings.presets == (), "a hand-edited built_in was accepted"
    assert read.problem is not None and "built_in" in read.problem.reason, read.problem


def test_one_malformed_preset_is_reported_and_the_rest_survive(tmp_path: Path) -> None:
    """`ARC-008`: something discarded is *reported*, not that everything is discarded.

    Dropping all ten presets because the tenth has a typo punishes a user for the typo. Asserted
    with the good one *after* the bad, because a loop that stopped at the first failure would pass
    the other way round.
    """
    target = tmp_path / "settings.toml"
    save(add_preset(Settings(concurrency=7), a_preset(name="Good")), target)
    target.write_text(
        target.read_text(encoding="utf-8")
        + '\n[[preset]]\nname = "Broken"\nmedia_kind = "nonsense"\n'
        'format_selector = "best"\noutput_template = "%(title)s.%(ext)s"\n',
        encoding="utf-8",
    )

    read = load(target)

    assert [preset.name for preset in read.settings.presets] == ["Good"]
    assert read.settings.concurrency == 7, "a bad preset reset the setting beside it"
    assert read.problem is not None
    assert "Broken" in read.problem.reason, read.problem.reason


def _preset_table(name: str, selector: str = "worst") -> str:
    """A syntactically valid `[[preset]]` entry, so only its *name* is in question."""
    return (
        f'\n[[preset]]\nname = "{name}"\nmedia_kind = "video"\n'
        f'format_selector = "{selector}"\noutput_template = "%(title)s.%(ext)s"\n'
    )


def test_a_hand_edited_preset_cannot_shadow_a_built_in(tmp_path: Path) -> None:
    """**`T111-R2`.** A saved entry taking a built-in's name is refused at the load boundary.

    This loaded clean before: `problem=None`, two rows of one name in the manager, and
    `preset_named` answering with the built-in while the saved row held a different selector. Every
    operation this module offers addresses a preset by name, so the duplicate is a row the code
    cannot address correctly rather than a cosmetic one.
    """
    shadowed = preset_registry.BUILT_IN_PRESETS[0].name
    target = tmp_path / "settings.toml"
    save(add_preset(Settings(), a_preset(name="Mine")), target)
    target.write_text(
        target.read_text(encoding="utf-8") + _preset_table(shadowed), encoding="utf-8"
    )

    read = load(target)

    assert [preset.name for preset in read.settings.presets] == ["Mine"], (
        "a saved preset shadowed a built-in's name; every name-addressed operation is now ambiguous"
    )
    assert read.problem is not None, "ARC-008: something was discarded and nothing said so"
    assert shadowed in read.problem.reason, read.problem.reason
    assert preset_named(read.settings, shadowed) == preset_registry.BUILT_IN_PRESETS[0]


def test_two_saved_presets_cannot_share_one_name(tmp_path: Path) -> None:
    """**`T111-R2`**, the saved/saved half. The earlier entry wins, so the file's order decides."""
    target = tmp_path / "settings.toml"
    save(add_preset(Settings(), a_preset(name="Keeper")), target)
    target.write_text(
        target.read_text(encoding="utf-8") + _preset_table("Keeper", selector="worst"),
        encoding="utf-8",
    )

    read = load(target)

    assert len(read.settings.presets) == 1, "two saved presets kept one name between them"
    kept = read.settings.presets[0]
    assert kept.format_selector != "worst", (
        "the later duplicate won; earlier entries must win so the answer does not depend on which "
        "duplicate was written last"
    )
    assert read.problem is not None and "Keeper" in read.problem.reason


def test_a_colliding_entry_does_not_cost_the_entries_around_it(tmp_path: Path) -> None:
    """`ARC-008` again: the collision is dropped, and the presets either side of it survive."""
    target = tmp_path / "settings.toml"
    save(add_preset(Settings(concurrency=7), a_preset(name="First")), target)
    target.write_text(
        target.read_text(encoding="utf-8") + _preset_table("First") + _preset_table("Third"),
        encoding="utf-8",
    )

    read = load(target)

    assert [preset.name for preset in read.settings.presets] == ["First", "Third"], (
        "a colliding entry took an innocent one with it"
    )
    assert read.settings.concurrency == 7, "a colliding preset reset the setting beside it"
    assert read.problem is not None


def test_a_file_with_no_collisions_reports_nothing(tmp_path: Path) -> None:
    """The anti-vacuity half: the new check must not report a file that is simply fine."""
    target = tmp_path / "settings.toml"
    save(add_preset(add_preset(Settings(), a_preset(name="One")), a_preset(name="Two")), target)

    read = load(target)

    assert [preset.name for preset in read.settings.presets] == ["One", "Two"]
    assert read.problem is None, read.problem


def test_a_broken_queue_section_does_not_cost_the_user_their_presets(tmp_path: Path) -> None:
    """The two halves are read independently, and both reasons are reported when both apply."""
    target = tmp_path / "settings.toml"
    save(add_preset(Settings(), a_preset(name="Good")), target)
    target.write_text(
        target.read_text(encoding="utf-8").replace("concurrency = 3", 'concurrency = "three"'),
        encoding="utf-8",
    )

    read = load(target)

    assert [preset.name for preset in read.settings.presets] == ["Good"]
    assert read.settings.concurrency == CONCURRENCY_DEFAULT
    assert read.problem is not None and "concurrency" in read.problem.reason


def test_saving_the_concurrency_limit_keeps_the_presets(tmp_path: Path) -> None:
    """`save()` writes the whole file, so two writers can erase each other (`_Held`'s reason).

    Asserted here rather than only in composition, because the property belongs to this module: a
    caller that saves a `Settings` carrying presets must get the presets back.
    """
    target = tmp_path / "settings.toml"
    stored = add_preset(Settings(), a_preset(name="Good"))
    save(stored, target)

    save(with_concurrency(load(target).settings, 9), target)

    read = load(target)
    assert [preset.name for preset in read.settings.presets] == ["Good"]
    assert read.settings.concurrency == 9


def test_a_file_with_no_presets_reports_nothing(tmp_path: Path) -> None:
    """The ordinary case, and the one an over-eager reader breaks."""
    target = tmp_path / "settings.toml"
    save(Settings(concurrency=4), target)

    read = load(target)

    assert read.problem is None
    assert read.settings.presets == ()


# --- T109-R9: a save that failed must not be reported as one -----------------------------------


def test_a_name_carrying_a_control_character_does_not_destroy_the_file(tmp_path: Path) -> None:
    """**`T109-R9`.** A `QLineEdit` keeps whatever is pasted into it.

    TOML forbids a raw control character in a basic string, so a name containing `\\x08` produced a
    file `tomllib` refused — and the *next* `load()` therefore returned **no presets** and reset the
    concurrency limit to its default. One bad character in one name destroyed unrelated settings.

    Escaping by codepoint is total: there is no name the UI accepts that this cannot represent, and
    the assertion is on the round trip rather than on the escaping, because the round trip is the
    property.
    """
    target = tmp_path / "settings.toml"
    settled = add_preset(Settings(concurrency=7), a_preset(name="Weekend"))
    save(settled, target)

    assert (
        save(add_preset(load(target).settings, a_preset(name="bad\x08name\x00here")), target)
        is None
    )

    read = load(target)
    assert read.problem is None, read.problem
    assert [preset.name for preset in read.settings.presets] == ["Weekend", "bad\x08name\x00here"]
    assert read.settings.concurrency == 7, (
        "an unreadable file reset the concurrency limit — the setting beside the bad name"
    )


@pytest.mark.parametrize(
    "name", ["tab\there", "line\nbreak", "carriage\rreturn", "del\x7f", "\x1b"]
)
def test_every_control_character_survives_the_round_trip(tmp_path: Path, name: str) -> None:
    """Totality, over the shapes a paste can actually produce."""
    target = tmp_path / "settings.toml"

    save(add_preset(Settings(), a_preset(name=name)), target)

    read = load(target)
    assert read.problem is None, read.problem
    assert [preset.name for preset in read.settings.presets] == [name]


def test_a_write_that_cannot_happen_says_so(tmp_path: Path) -> None:
    """**`T109-R9`'s other half**: `save()` swallowed every `OSError` and told nobody.

    The non-fatal policy is right — a read-only config directory is a real deployment state and not
    a reason the application cannot start — and it was never a reason for a *caller* to be told the
    write succeeded. `P-4`'s *Save as preset…* said `Saved as Weekend viewing.` over a preset that
    reached no disk.
    """
    unwritable = tmp_path / "settings.toml"
    unwritable.mkdir()

    failure = save(Settings(), unwritable)

    assert failure is not None, "an impossible write reported success"
    assert "Error" in failure, failure


def test_a_successful_write_says_nothing(tmp_path: Path) -> None:
    """`None` means written, so a caller cannot read a failure into an ordinary save."""
    assert save(Settings(), tmp_path / "settings.toml") is None


def test_a_failed_write_leaves_the_previous_file_intact(tmp_path: Path) -> None:
    """Written beside the file and moved onto it, so the file is the old one or the new one.

    `write_text` truncates first, so a write that fails partway leaves a truncated file where
    working settings used to be — and the next `load()` reports the user's own presets as
    unreadable, which is the same data loss the escaping defect caused by another route.
    """
    target = tmp_path / "settings.toml"
    save(add_preset(Settings(concurrency=6), a_preset(name="Weekend")), target)
    before = target.read_text(encoding="utf-8")

    # A scratch path that cannot be created: the directory it would sit in is occupied by a file
    # of the same name, which is the closest deterministic stand-in for a full disk.
    (tmp_path / "settings.toml.writing").mkdir()
    failure = save(add_preset(load(target).settings, a_preset(name="Second")), target)

    assert failure is not None
    assert target.read_text(encoding="utf-8") == before, "a failed write damaged the good file"
    assert [preset.name for preset in load(target).settings.presets] == ["Weekend"]


# --- T-111: the five operations REQ-007 names -----------------------------------------------
#
# `add_preset` is create and was built by `T-109` as `P-4`'s seam; the four below are the rest.
# Every case asserts on **what is stored afterwards** rather than on the return value alone,
# which is this task's first acceptance criterion.


def test_editing_a_saved_preset_replaces_it_in_place() -> None:
    """Edit, asserted on the stored list — and on the *position*, which is easy to lose.

    Rebuilding the tuple by filtering and appending would pass a "the edit is stored" assertion
    while quietly moving the preset to the end. The list is in the order the user saved them, and
    an edit is not a save.
    """
    settings = add_preset(add_preset(Settings(), a_preset(name="First")), a_preset(name="Second"))

    edited = update_preset(settings, "First", a_preset(name="First", audio_quality="320"))

    assert [preset.name for preset in edited.presets] == ["First", "Second"]
    assert edited.presets[0].audio_quality == "320"


def test_editing_can_rename_and_the_new_name_is_what_is_stored() -> None:
    settings = add_preset(Settings(), a_preset(name="Weekend viewing"))

    edited = update_preset(settings, "Weekend viewing", a_preset(name="Weeknight viewing"))

    assert [preset.name for preset in edited.presets] == ["Weeknight viewing"]


def test_editing_into_a_name_already_taken_is_refused() -> None:
    """The same rule `add_preset` applies, at the other door into the same list.

    A rename is a creation as far as the name is concerned, and a check on one path only is how
    two presets end up sharing a name that `REQ-009` promises identifies the download.
    """
    settings = add_preset(add_preset(Settings(), a_preset(name="First")), a_preset(name="Second"))

    with pytest.raises(ValueError, match="already exists"):
        update_preset(settings, "First", a_preset(name="Second"))


def test_editing_into_a_built_ins_name_is_refused() -> None:
    settings = add_preset(Settings(), a_preset(name="Mine"))

    with pytest.raises(ValueError, match="already exists"):
        update_preset(settings, "Mine", a_preset(name=preset_registry.AUDIO_MP3.name))


def test_a_preset_may_be_edited_without_renaming_it() -> None:
    """The collision check must not fire on the preset's *own* name, which is the obvious trap."""
    settings = add_preset(Settings(), a_preset(name="Weekend viewing"))

    edited = update_preset(
        settings, "Weekend viewing", a_preset(name="Weekend viewing", embed_metadata=True)
    )

    assert edited.presets[0].embed_metadata is True


def test_a_built_in_cannot_be_edited_and_the_refusal_says_what_to_do_instead() -> None:
    """`REQ-006`/`REQ-009`: a built-in edited in place no longer matches the name it ships under.

    `docs/UX_SPEC.md` §8 makes duplication the way to start from one, so the refusal names it —
    a caller reading this message does not have to find the route themselves.
    """
    with pytest.raises(ValueError, match="built-in"):
        update_preset(Settings(), preset_registry.AUDIO_MP3.name, a_preset(name="Anything"))


def test_editing_an_unknown_preset_is_refused() -> None:
    with pytest.raises(ValueError, match="no saved preset"):
        update_preset(Settings(), "Never existed", a_preset())


def test_deleting_removes_it_from_what_is_stored() -> None:
    settings = add_preset(add_preset(Settings(), a_preset(name="First")), a_preset(name="Second"))

    assert [preset.name for preset in remove_preset(settings, "First").presets] == ["Second"]


def test_a_built_in_cannot_be_deleted() -> None:
    """`docs/UX_SPEC.md` §8: built-ins are marked as undeletable rather than drawn disabled."""
    with pytest.raises(ValueError, match="built-in"):
        remove_preset(Settings(), preset_registry.AUDIO_MP3.name)


def test_deleting_an_unknown_preset_is_refused() -> None:
    with pytest.raises(ValueError, match="no saved preset"):
        remove_preset(Settings(), "Never existed")


def test_duplicating_stores_a_copy_under_a_free_name() -> None:
    settings = add_preset(Settings(), a_preset(name="Weekend viewing", audio_quality="320"))

    duplicated, copy = duplicate_preset(settings, "Weekend viewing")

    assert copy.name == "Weekend viewing (copy)"
    assert copy.audio_quality == "320", "the copy did not carry the original's fields"
    assert [preset.name for preset in duplicated.presets] == [
        "Weekend viewing",
        "Weekend viewing (copy)",
    ]


def test_duplicating_a_built_in_is_how_you_start_from_one() -> None:
    """The other half of the built-in rule, and the reason editing one can be refused at all."""
    duplicated, copy = duplicate_preset(Settings(), preset_registry.AUDIO_MP3.name)

    assert copy.name == f"{preset_registry.AUDIO_MP3.name} (copy)"
    assert copy.built_in is False, "a duplicate of a built-in would claim to ship with the app"
    assert copy.format_selector == preset_registry.AUDIO_MP3.format_selector
    assert duplicated.presets == (copy,)


def test_duplicating_twice_keeps_finding_a_free_name() -> None:
    """A second copy must not collide with the first, which `add_preset` would refuse outright."""
    settings, _ = duplicate_preset(Settings(), preset_registry.AUDIO_MP3.name)
    settings, second = duplicate_preset(settings, preset_registry.AUDIO_MP3.name)

    assert second.name == f"{preset_registry.AUDIO_MP3.name} (copy 2)"


def test_duplicating_an_unknown_preset_is_refused() -> None:
    with pytest.raises(ValueError, match="no preset called"):
        duplicate_preset(Settings(), "Never existed")


def test_a_free_name_is_the_base_itself_when_nothing_holds_it() -> None:
    assert free_preset_name(Settings(), "Nothing has this") == "Nothing has this"


def test_setting_a_default_stores_the_name() -> None:
    settings = add_preset(Settings(), a_preset(name="Weekend viewing"))

    assert set_default_preset(settings, "Weekend viewing").default_preset == "Weekend viewing"


def test_a_built_in_may_be_the_default() -> None:
    """`P-7` is about there always being one, not about whose it is."""
    chosen = set_default_preset(Settings(), preset_registry.AUDIO_MP3.name)

    assert default_preset_of(chosen) == preset_registry.AUDIO_MP3


def test_setting_an_unknown_default_is_refused() -> None:
    with pytest.raises(ValueError, match="no preset called"):
        set_default_preset(Settings(), "Never existed")


# --- T-111: P-7 — always exactly one default ------------------------------------------------


def test_a_fresh_install_already_has_a_default() -> None:
    """*Always exactly one, always set*: the dialog needs something to inherit on first run."""
    assert default_preset_of(Settings()) == preset_registry.BUILT_IN_PRESETS[0]


def test_the_default_survives_a_restart(tmp_path: Path) -> None:
    """This task's fourth criterion, read through the file rather than around it."""
    target = tmp_path / "settings.toml"
    settings = add_preset(Settings(), a_preset(name="Weekend viewing"))

    save(set_default_preset(settings, "Weekend viewing"), target)
    read = load(target)

    assert read.problem is None, read.problem
    assert read.settings.default_preset == "Weekend viewing"
    assert default_preset_of(read.settings).name == "Weekend viewing"


def test_a_built_in_default_survives_a_restart(tmp_path: Path) -> None:
    """The default may name a preset that has no `[[preset]]` table of its own to be written in."""
    target = tmp_path / "settings.toml"

    save(set_default_preset(Settings(), preset_registry.AUDIO_MP3.name), target)

    assert load(target).settings.default_preset == preset_registry.AUDIO_MP3.name


def test_deleting_the_default_leaves_a_defined_default() -> None:
    """The rest of the fourth criterion. Deleting a preset must not leave the field dangling."""
    settings = set_default_preset(
        add_preset(Settings(), a_preset(name="Weekend viewing")), "Weekend viewing"
    )

    after = remove_preset(settings, "Weekend viewing")

    assert after.default_preset == "", "the stored name still points at a deleted preset"
    assert default_preset_of(after) == preset_registry.BUILT_IN_PRESETS[0]


def test_deleting_a_different_preset_leaves_the_default_alone() -> None:
    settings = add_preset(add_preset(Settings(), a_preset("Keep")), a_preset("Drop"))

    after = remove_preset(set_default_preset(settings, "Keep"), "Drop")

    assert after.default_preset == "Keep"


def test_renaming_the_default_carries_the_default_with_it() -> None:
    """A rename is not a deletion, and must not behave like one.

    The default is stored as a name, so renaming the preset holding it would otherwise leave the
    field naming nothing — handing the user back the registry's first preset for what they
    experienced as an edit.
    """
    settings = set_default_preset(
        add_preset(Settings(), a_preset(name="Weekend viewing")), "Weekend viewing"
    )

    after = update_preset(settings, "Weekend viewing", a_preset(name="Weeknight viewing"))

    assert after.default_preset == "Weeknight viewing"
    assert default_preset_of(after).name == "Weeknight viewing"


def test_a_default_naming_nothing_is_reported_and_falls_back(tmp_path: Path) -> None:
    """`ARC-008`, and this task's sixth criterion: a hand-edit reports rather than reverting.

    The commonest route here is worth naming — a preset earlier in the same file was malformed,
    was dropped, and was the one the default named.
    """
    target = write(tmp_path, 'default_preset = "Gone"\n[queue]\nconcurrency = 4\n')

    read = load(target)

    assert read.problem is not None, "a discarded choice was not reported"
    assert "Gone" in read.problem.reason
    assert read.settings.concurrency == 4, "an unusable default cost the setting beside it"
    assert default_preset_of(read.settings) == preset_registry.BUILT_IN_PRESETS[0]


def test_a_default_that_is_not_a_name_is_reported(tmp_path: Path) -> None:
    target = write(tmp_path, "default_preset = 3\n[queue]\nconcurrency = 4\n")

    read = load(target)

    assert read.problem is not None
    assert "not a preset name" in read.problem.reason
    assert read.settings.concurrency == 4


def test_a_file_that_omits_the_default_reports_nothing(tmp_path: Path) -> None:
    """Omission stays silent, because the file this application writes promises it does."""
    target = write(tmp_path, "[queue]\nconcurrency = 4\n")

    assert load(target).problem is None


def test_settings_refuses_a_default_that_is_not_a_name_in_code() -> None:
    """A file is corrected; a caller is not. The same split every other field here follows."""
    with pytest.raises(TypeError, match="default_preset"):
        Settings(default_preset=3)  # type: ignore[arg-type]


# --- T-111: the one list the manager shows --------------------------------------------------


def test_all_presets_puts_the_built_ins_first_and_the_users_after() -> None:
    """`P-6`: one list holding both, with the built-ins marked — not two lists."""
    settings = add_preset(Settings(), a_preset(name="Mine"))

    listed = all_presets(settings)

    assert listed[: len(preset_registry.BUILT_IN_PRESETS)] == preset_registry.BUILT_IN_PRESETS
    assert listed[-1].name == "Mine"
    assert [preset.built_in for preset in listed][-1] is False


def test_preset_named_finds_both_kinds_and_answers_none_for_neither() -> None:
    settings = add_preset(Settings(), a_preset(name="Mine"))

    assert preset_named(settings, "Mine") is not None
    assert preset_named(settings, preset_registry.AUDIO_MP3.name) == preset_registry.AUDIO_MP3
    assert preset_named(settings, "Never existed") is None


# --- T-146: the download folder and the theme -------------------------------------------------


def test_a_stored_download_folder_is_used_as_written(tmp_path: Path) -> None:
    """The ordinary case: a folder that exists and can be written to is the answer."""
    folder = tmp_path / "Trail recordings"
    folder.mkdir()
    target = write(tmp_path, f"[downloads]\ndirectory = {toml_path(folder)}\n")

    read = load(target)

    assert read.settings.download_directory == folder
    assert read.problem is None


def test_a_download_folder_that_is_gone_reports_and_falls_back(tmp_path: Path) -> None:
    """**`ARC-008` and `T-146`'s criterion**: report rather than revert silently.

    Reported *and* fallen back from, which is the pair `ARC-008` asks for — the application still
    starts, and the user is told their folder is not there rather than finding files somewhere
    else without explanation.

    **Not recreated.** The picker only offers folders that exist, so a stored one that is gone was
    deleted or lives on a drive that is not mounted; making an empty folder in its place would
    answer a question nobody asked and hide the likelier cause.
    """
    missing = tmp_path / "on-a-drive-that-is-not-mounted"
    target = write(tmp_path, f"[downloads]\ndirectory = {toml_path(missing)}\n")

    read = load(target)

    assert read.settings.download_directory is None
    assert read.problem is not None
    assert str(missing) in read.problem.reason
    assert not missing.exists(), "a missing download folder was recreated rather than reported"


def test_a_download_folder_that_is_a_file_reports_and_falls_back(tmp_path: Path) -> None:
    a_file = tmp_path / "not-a-folder.txt"
    a_file.write_text("", encoding="utf-8")
    target = write(tmp_path, f"[downloads]\ndirectory = {toml_path(a_file)}\n")

    read = load(target)

    assert read.settings.download_directory is None
    assert read.problem is not None and "not a folder" in read.problem.reason


def test_a_download_folder_that_cannot_be_written_reports_and_falls_back(tmp_path: Path) -> None:
    """A read-only folder is a real deployment state — a mounted share, someone else's directory.

    Skipped as root, which bypasses the permission bits entirely and would make this assert that
    `os.access` agrees with itself.
    """
    # Asked of the attribute rather than of `sys.platform`, which mypy narrows under
    # `--platform win32` until everything after it is unreachable.
    effective_user = getattr(os, "geteuid", None)
    if effective_user is None:
        pytest.skip("POSIX permission bits are not how Windows refuses a write")
    if effective_user() == 0:
        pytest.skip("root ignores the permission bits this asserts on")
    locked = tmp_path / "read-only"
    locked.mkdir(mode=0o500)
    target = write(tmp_path, f"[downloads]\ndirectory = {toml_path(locked)}\n")
    try:
        read = load(target)
    finally:
        locked.chmod(0o700)

    assert read.settings.download_directory is None
    assert read.problem is not None and "cannot be written to" in read.problem.reason


def test_an_absent_or_empty_download_folder_is_silent(tmp_path: Path) -> None:
    """Omission is silent, because `save()`'s header promises deleting a line is safe."""
    assert load(write(tmp_path, "[queue]\nconcurrency = 3\n")).problem is None
    empty = load(write(tmp_path, '[downloads]\ndirectory = ""\n'))
    assert empty.settings.download_directory is None
    assert empty.problem is None, "an empty folder value was reported as a broken setting"


def test_a_download_folder_that_is_not_a_string_reports(tmp_path: Path) -> None:
    read = load(write(tmp_path, "[downloads]\ndirectory = 7\n"))

    assert read.settings.download_directory is None
    assert read.problem is not None and "not a path" in read.problem.reason


def test_a_theme_is_read_and_an_unknown_one_is_reported(tmp_path: Path) -> None:
    """Unknown names are refused rather than clamped: two palettes have no nearest neighbour."""
    assert load(write(tmp_path, '[appearance]\ntheme = "dark"\n')).settings.theme == "dark"

    read = load(write(tmp_path, '[appearance]\ntheme = "solarized"\n'))
    assert read.settings.theme == THEME_DEFAULT
    assert read.problem is not None and "solarized" in read.problem.reason


def test_a_broken_theme_does_not_cost_the_user_their_download_folder(tmp_path: Path) -> None:
    """**Read independently, reported together** — `T109-R5`'s rule, extended to `T-146`'s keys."""
    folder = tmp_path / "kept"
    folder.mkdir()
    read = load(
        write(
            tmp_path, f"[downloads]\ndirectory = {toml_path(folder)}\n\n[appearance]\ntheme = 3\n"
        )
    )

    assert read.settings.download_directory == folder, (
        "an unreadable theme discarded a perfectly good download folder"
    )
    assert read.settings.theme == THEME_DEFAULT
    assert read.problem is not None


def test_the_folder_and_the_theme_survive_a_save_and_load(tmp_path: Path) -> None:
    """The round trip, which is what "survives a restart" means at this layer."""
    folder = tmp_path / "Trail recordings"
    folder.mkdir()
    target = tmp_path / "settings.toml"
    settings = with_theme(with_download_directory(Settings(), folder), "dark")

    assert save(settings, target) is None
    read = load(target)

    assert read.problem is None
    assert read.settings.download_directory == folder
    assert read.settings.theme == "dark"


def test_saving_the_folder_and_theme_keeps_the_presets_readable(tmp_path: Path) -> None:
    """All three kinds of setting coexist in one file, and all three come back.

    `T-146` adds two sibling tables to a file that already holds an array of tables, and the
    round trip is what proves the writer did not corrupt the reader's view of either.

    **What this does *not* prove, stated because the first draft claimed it did:** that the
    tables must precede `[[preset]]`. A TOML table header is an absolute path from the root, so
    writing them afterwards round-trips just as well — mutating `save()` to emit them last leaves
    this test green. The order is for whoever opens the file, and `save()` says so.
    """
    folder = tmp_path / "Trail recordings"
    folder.mkdir()
    target = tmp_path / "settings.toml"
    settings = add_preset(
        with_theme(with_download_directory(Settings(), folder), "dark"), a_preset(name="Mine")
    )

    assert save(settings, target) is None
    read = load(target)

    assert read.problem is None, read.problem
    assert read.settings.download_directory == folder
    assert read.settings.theme == "dark"
    assert [preset.name for preset in read.settings.presets] == ["Mine"]


def test_with_theme_refuses_a_name_this_application_does_not_have() -> None:
    """Bounded at the value, exactly as `with_concurrency` bounds a number."""
    assert with_theme(Settings(), "dark").theme == "dark"
    assert with_theme(Settings(), "solarized").theme == THEME_DEFAULT
    assert set(THEME_NAMES) == {"light", "dark"}


# --- T146-R1: load() never raises, including while expanding a path ---------------------------


def test_a_download_folder_naming_another_users_home_reports_and_falls_back(
    tmp_path: Path,
) -> None:
    """**`T146-R1`, asserted as the contract rather than as one platform's branch** (`T146-R3`).

    A settings file naming `~someone-who-left/downloads` must leave the application startable, on
    a folder it can use, having said what it discarded. **Which branch produces that differs by
    platform, and the first version of this test asserted the POSIX one**: there,
    `Path.expanduser()` raises `RuntimeError` because no `pwd` entry exists, so the guard reports
    *could not be checked*. On Windows `ntpath.expanduser` guesses a sibling of `%USERPROFILE%`
    instead, the path resolves to something that simply is not there, and the *missing folder*
    branch reports — so the old assertion failed the Windows job, which runs the whole suite
    (`T146-R3`; `AGENTS.md` §8's asymmetry, caught in review rather than by me).

    So this asserts what is true either way: fell back, reported, and the report identifies the
    folder. The user name is what both messages carry — verbatim in one, inside the guessed path
    in the other — so it is the portable way to ask "does this name what it discarded?".
    """
    target = write(tmp_path, '[downloads]\ndirectory = "~nosuchuser12345/downloads"\n')

    read = load(target)

    assert read.settings.download_directory is None, (
        "an unusable folder was accepted, so downloads would go somewhere unwritable"
    )
    assert read.problem is not None, "an unusable folder was discarded silently (ARC-008)"
    assert "nosuchuser12345" in read.problem.reason, (
        f"the report does not identify the folder it discarded: {read.problem.reason!r}"
    )


@pytest.mark.skipif(
    os.name != "posix",
    reason=(
        "the RuntimeError branch needs an expansion that cannot resolve a home, which is POSIX's "
        "answer for an unknown ~user; Windows guesses a path instead and reaches the missing-"
        "folder branch, which the portable test above covers"
    ),
)
def test_an_expansion_that_cannot_resolve_a_home_is_caught_rather_than_raised(
    tmp_path: Path,
) -> None:
    """**`T146-R1`'s own branch**, where it can be reached without asserting a guess.

    `Path("~nosuchuser/x").expanduser()` raises `RuntimeError` on POSIX, and that call sat
    *outside* the guard — so it left `load()`, broke the never-raises contract, and **stopped the
    application starting** on a file `ARC-008` exists to report. Reproduced against the real
    function before the guard was moved; moving it back out fails this.

    **Skipped rather than forced on Windows.** Reaching this branch there would mean deleting
    `%USERPROFILE%` and `%HOMEPATH%` so the expansion gives up — behaviour I reasoned from
    CPython's source and cannot run here, which is exactly the kind of claim `T146-R3` was. The
    guard itself is platform-independent code; what Windows proves is the outcome, above.

    The reported text names the value **as written**: when the expansion is what failed, there is
    no expanded path to show, and printing a half-expanded one would be worse than printing none.
    """
    target = write(tmp_path, '[downloads]\ndirectory = "~nosuchuser12345/downloads"\n')

    read = load(target)

    assert read.problem is not None
    assert "could not be checked" in read.problem.reason, (
        f"the expansion failure took a different branch than expected: {read.problem.reason!r}"
    )
    assert "~nosuchuser12345/downloads" in read.problem.reason, (
        f"the report does not name the value the user wrote: {read.problem.reason!r}"
    )


def test_every_settings_file_shape_leaves_the_application_startable(tmp_path: Path) -> None:
    """The contract itself, over every shape this module has ever had to survive.

    `load()`'s docstring says *never raises*, and each entry below is a file that once could or
    still could break it. Asserted as one sweep because the promise is about the function, not
    about any single branch of it.
    """
    shapes = [
        '[downloads]\ndirectory = "~nosuchuser12345/x"\n',
        # A raw NUL: `tomllib` refuses it while parsing on every platform, so it never
        # reaches the path code. Written without a platform-shaped prefix to say so.
        '[downloads]\ndirectory = "nul\x00byte"\n',
        "[downloads]\ndirectory = 7\n",
        '[downloads]\ndirectory = ""\n',
        "[downloads]\ndirectory = { nested = true }\n",
        "downloads = 5\n",
        '[appearance]\ntheme = "solarized"\n',
        "[appearance]\ntheme = 3\n",
        "appearance = 5\n",
        "[queue]\nconcurrency = ",
        "<<<not toml>>>",
        "",
    ]
    for body in shapes:
        target = write(tmp_path, body)
        read = load(target)
        assert isinstance(read.settings, Settings), f"{body!r} did not answer with settings"
