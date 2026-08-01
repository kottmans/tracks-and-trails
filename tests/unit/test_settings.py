"""`core/settings.py` — the bounds `REQ-013` states and the failures a hand-edited file can hold.

`ARC-007` puts the concurrency limit in `settings.toml` and puts the *bound* here rather than on
the control that edits it. `T-078`'s criteria say why: a spinbox clamping its own input bounds the
widget, and the file is hand-editable by design, so `concurrency = 0` must not reach the pool.

No Qt and no network, per `tests/` layout. This module is `core/`.
"""

from pathlib import Path

import pytest

from tracks_and_trails.core.settings import (
    CONCURRENCY_DEFAULT,
    CONCURRENCY_MAXIMUM,
    CONCURRENCY_MINIMUM,
    Settings,
    load,
    save,
    settings_path,
    with_concurrency,
)


def write(path: Path, body: str) -> Path:
    target = path / "settings.toml"
    target.write_text(body, encoding="utf-8")
    return target


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
