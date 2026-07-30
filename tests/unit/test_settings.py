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
    assert load(tmp_path / "nothing-here.toml") == Settings()


def test_a_directory_where_the_file_should_be_yields_the_defaults(tmp_path: Path) -> None:
    """`OSError` rather than a parse failure, and the same answer. A real state after a bad copy."""
    (tmp_path / "settings.toml").mkdir()
    assert load(tmp_path / "settings.toml") == Settings()


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
    assert load(write(tmp_path, body)) == Settings(), f"{name} did not fall back to defaults"


def test_a_valid_file_is_used_as_written(tmp_path: Path) -> None:
    assert load(write(tmp_path, "[queue]\nconcurrency = 7\n")).concurrency == 7


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
    limit = load(write(tmp_path, f"[queue]\nconcurrency = {written}\n")).concurrency
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
    limit = load(write(tmp_path, f"[queue]\nconcurrency = {written}\n")).concurrency
    assert limit == CONCURRENCY_MAXIMUM
    assert limit != CONCURRENCY_DEFAULT, "a value above the ceiling fell back to the default"


def test_the_boundaries_themselves_survive_a_round_trip(tmp_path: Path) -> None:
    """Neither bound may be off by one; each is a value a user can legitimately choose."""
    assert load(write(tmp_path, "[queue]\nconcurrency = 1\n")).concurrency == 1
    assert load(write(tmp_path, "[queue]\nconcurrency = 16\n")).concurrency == 16


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
    got = load(write(tmp_path, f"[queue]\nconcurrency = {literal}\n")).concurrency
    assert got == CONCURRENCY_DEFAULT, f"{name} produced {got}"


# --- round trip and the write path ---------------------------------------------------------


def test_saved_settings_load_back_identically(tmp_path: Path) -> None:
    """Whole-object comparison, so a field added later that `save` forgets fails here."""
    target = tmp_path / "settings.toml"
    original = Settings(concurrency=5)
    save(original, target)
    assert load(target) == original


def test_saving_creates_the_directory_it_needs(tmp_path: Path) -> None:
    """First run writes into a config directory that does not exist yet."""
    target = tmp_path / "nested" / "deeper" / "settings.toml"
    save(Settings(concurrency=2), target)
    assert load(target).concurrency == 2


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
