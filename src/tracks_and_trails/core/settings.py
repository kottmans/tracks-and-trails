"""Settings schema, defaults, validation, and TOML load/save (`DAT-001`, `ARC-007`).

**`ARC-007` decided the shape of this module before any of it existed.** `DAT-001` chose TOML;
`ARCHITECTURE.md` §5 places the file at `user_config_dir/tracksandtrails/settings.toml` and assigns
it here. Phase 2 lands the layer with one key — the concurrency limit — and Phase 4's `REQ-023`
dialog adds keys on top of it rather than replacing it.

## Nothing downstream reads this module

`downloader/manager.py` receives an integer and a way to be told it changed; composition and the
UI own the file (`ARC-007`). That is `JobStore`'s shape again — the manager depends on a value, not
on a config format — and it is what keeps the pool testable without TOML on disk.
`tests/unit/test_manager_boundaries.py` enforces it (`T-097`), because the layering test permits
`downloader/` → `core/` and would not.

## Bounds live here, not in the widget

`REQ-013` says *default 3, minimum 1*. A spinbox that clamps its own input bounds **the widget**,
not the file: `settings.toml` is hand-editable by design, so a `0` typed into it must not produce a
pool that starts nothing. Every bound is applied on the way out of `load()`, so there is exactly
one place a value can be wrong and one place it is corrected. `T-044`, `T-045` and `T-014` are
three rounds of the same lesson — constrain what the value can be rather than filtering what
arrives.

## Reading never fails, and no longer fails quietly

A missing file is the normal first run. An unparseable one is a hand-edit that went wrong, a partial
write, or a file from a future version. None of those is a reason the application cannot start, so
`load()` answers with defaults and `save()` swallows `OSError` — the same rule
`ui/main_window.py.save_geometry` follows for `window.toml`, and for the same reason: a read-only
config directory is a real deployment state.

**A file that exists and cannot be used now says so** (`ARC-008`, `T-102`). The fallback is
unchanged; the silence is what went. `load()` answers with a `SettingsFile` carrying both the
settings in force and, when something was discarded, a `SettingsProblem` describing it — as
**data**, because `core/**` may not import Qt and this runs in composition before any window
exists. `ui/` presents it.

`SettingsProblem.summary` is composed here rather than in the widget so the words a user reads are
testable with no display attached, which is the property the layering rule exists to protect.

*(This section used to end: "**What that gives up, stated:** a corrupt file is silently replaced by
defaults rather than reported. Nothing in `REQ-023` or `ARC-007` asks for a settings-parse
diagnostic, and there is nowhere to show one until Phase 4's dialog exists." Both halves of that
justification had weakened — `T-078` shipped a main-window control, so there **is** somewhere to
show one, and `save()` writes the file that control edits. `ARC-008` decided it; the paragraph is
deleted rather than amended, because it described behaviour that no longer exists.)*
"""

import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final

from platformdirs import user_config_dir

#: Duplicated from `downloader/environment.py` and `ui/main_window.py`, which each define their own.
#: Hoisting it into one place would touch two approved modules for no behavioural gain, so this
#: follows the existing precedent rather than starting a refactor inside `T-078`.
APP_SLUG: Final = "tracksandtrails"

#: `REQ-013`: *"a bounded, user-configurable number of downloads concurrently (default 3,
#: minimum 1)"*.
CONCURRENCY_DEFAULT: Final = 3
CONCURRENCY_MINIMUM: Final = 1

#: The ceiling `REQ-013` does not name (`ARC-007`, amended 2026-07-30).
#:
#: **It exists to catch a typo, not to model the hardware.** `REQ-013` says *bounded, minimum 1* and
#: names no maximum, so any positive integer was honoured verbatim — a `settings.toml` holding `30`
#: where `3` was meant asked for thirty spawned worker processes, and `ARC-002` makes each of
#: those a full interpreter with yt-dlp imported.
#:
#: **16 rather than a measurement.** Memory is not the binding constraint: a worker's baseline is
#: ~34 MiB measured, so even 64 of them is about 2 GiB. `os.cpu_count()` was rejected for the
#: opposite reason — downloads are I/O-bound, so cores are the wrong metric, and a two-core laptop
#: can usefully run more than two. What is left is a number generous enough never to obstruct a
#: deliberate choice on a desktop downloader whose default is 3, and low enough that an extra zero
#: does not survive.
CONCURRENCY_MAXIMUM: Final = 16

#: The TOML table every setting in this module lives under. One table now, because Phase 4 adds
#: siblings rather than nesting deeper.
_TABLE: Final = "queue"
_CONCURRENCY_KEY: Final = "concurrency"


def settings_path() -> Path:
    """`user_config_dir/tracksandtrails/settings.toml`, per `ARCHITECTURE.md` §5.

    `appauthor=False` is load-bearing on Windows and a no-op on Linux — without it platformdirs
    inserts an author segment defaulting to the app name, giving a doubled
    `%APPDATA%\\tracksandtrails\\tracksandtrails\\` that matches no path §5 specifies. The same
    reasoning, and the same argument, as `geometry_path()`.
    """
    return Path(user_config_dir(APP_SLUG, appauthor=False)) / "settings.toml"


@dataclass(frozen=True, slots=True)
class Settings:
    """The settings this application holds. Frozen, like every other model in `core/`.

    One field today. Phase 4's `REQ-023` adds the other seven; this is the type they land on.
    """

    concurrency: int = CONCURRENCY_DEFAULT

    def __post_init__(self) -> None:
        # A `Settings` built in code is held to the bound; a file is not. `load()` corrects what it
        # reads because a malformed file is not a programming error, and a caller passing 0 is.
        if isinstance(self.concurrency, bool) or not isinstance(self.concurrency, int):
            raise TypeError(
                f"Settings.concurrency must be an int, not {type(self.concurrency).__name__}"
            )
        if self.concurrency < CONCURRENCY_MINIMUM:
            raise ValueError(
                f"Settings.concurrency is {self.concurrency}; REQ-013's minimum is "
                f"{CONCURRENCY_MINIMUM}. A pool of zero starts nothing, which looks like a hang."
            )
        if self.concurrency > CONCURRENCY_MAXIMUM:
            raise ValueError(
                f"Settings.concurrency is {self.concurrency}; the ceiling is "
                f"{CONCURRENCY_MAXIMUM} (`ARC-007`). Each concurrent download is a spawned "
                "worker process, so a caller asking for more than this has a bug rather than a "
                "preference — a file asking for it is clamped instead."
            )


def _concurrency_from(raw: Any) -> int:
    """Coerce a value read from TOML into a usable limit. **Never raises.**

    Three outcomes, each deliberate and each named by `T-078`'s acceptance criteria:

    - **A valid integer** is used as written.
    - **An integer below the minimum** — `0`, a negative — is raised to `CONCURRENCY_MINIMUM` rather
      than replaced by the default. The user wrote a number whose evident intent is "as few as
      possible"; honouring that up to the bound respects the edit, where falling back to 3 discards
      it.
    - **An integer above the maximum** is lowered to `CONCURRENCY_MAXIMUM`, by the same reasoning
      read the other way: `30` says "a lot", and the most of "a lot" this application will do is 16.
      Clamped rather than rejected, because a file is not a caller — `Settings` still raises for a
      value out of range, since a caller passing 40 has a bug.
    - **Anything that is not an integer** — a string, a float, a boolean, a table — becomes
      `CONCURRENCY_DEFAULT`. There is no intent to honour: `"three"` and `2.5` do not say how many
      processes to run.

    `bool` is excluded explicitly because it is an `int` subclass, so `concurrency = true` would
    otherwise pass as `1`. Same trap `downloader/worker.py._int_or_none` avoids.

    **The maximum is this project's, not `REQ-013`'s** (`ARC-007`, amended 2026-07-30). The
    requirement says *bounded, minimum 1* and names no ceiling. Leaving it unbounded was compliant
    and was flagged rather than fixed, because inventing a requirement is worse than naming a gap —
    until the pool became real, at which point the gap stopped being theoretical and the maintainer
    ruled. `CONCURRENCY_MAXIMUM` documents the reasoning.
    """
    if isinstance(raw, bool) or not isinstance(raw, int):
        return CONCURRENCY_DEFAULT
    return min(max(raw, CONCURRENCY_MINIMUM), CONCURRENCY_MAXIMUM)


@dataclass(frozen=True, slots=True)
class SettingsProblem:
    """A settings file that exists and could not be used (`ARC-008`, `T-102`).

    **Data, not a dialog.** `core/**` may not import Qt (`AGENTS.md` §7) and `load()` runs in
    composition before any window exists, so the diagnostic travels back to the caller and `ui/`
    decides how to show it.
    """

    #: The file this is about. Named in the report, because a user who has more than one profile,
    #: or who edited the wrong copy, cannot act on "your settings file" alone.
    path: Path

    #: What went wrong, in the underlying layer's own words where it has any. A
    #: `TOMLDecodeError` carries a line and column, and discarding them would leave the reader no
    #: better off than the silence this replaces.
    reason: str

    @property
    def summary(self) -> str:
        """The sentence a user reads. Composed here so it is testable with no display attached."""
        return (
            f"Your settings file could not be read, so default settings are in use.\n\n"
            f"{self.path}\n{self.reason}\n\n"
            "Saving settings will overwrite this file."
        )


@dataclass(frozen=True, slots=True)
class SettingsFile:
    """What `load()` answers: the settings in force, and why they are not the file's.

    A pair rather than a bare `Settings`, so a caller cannot read the values and stay unaware that
    they are defaults standing in for a file somebody hand-edited wrongly. `problem` is `None` on
    every ordinary path, including the normal first run.
    """

    settings: Settings
    problem: SettingsProblem | None = None


def load(path: Path | None = None) -> SettingsFile:
    """Read settings from `path`. **Never raises**; unreadable or invalid means defaults.

    A missing file is the normal first run, and `tomllib` raising on a malformed one says the file
    is wrong rather than that the application is. Both answer with `Settings()`.

    **`ARC-008` decides which of those is reported**, and the line is whether something was
    *discarded* rather than whether the read was perfect:

    | The file | Reported |
    |---|---|
    | Does not exist | **No** — the normal first run |
    | Exists, cannot be opened or read | **Yes** |
    | Exists, is not valid TOML | **Yes** |
    | Parses, but `[queue]` is not a table | **Yes** |
    | Parses, `[queue]` is a table, `concurrency` is not an `int` | **Yes** |
    | Parses and simply omits `concurrency` | **No** |
    | Parses, `concurrency` is an `int` out of range | **No** — clamped, see `_concurrency_from` |

    **Omission is silent because `save()` promises it is.** The file this application writes says
    *"Safe to delete: every value falls back to its default."* A user who takes that at its word and
    deletes the line must not then be told their file is broken. An empty file and one with no
    `[queue]` table are the same case.

    **A missing file is told apart from an unreadable one**, rather than both landing in one
    `OSError` branch. They are the two most different cases this function has — one is every first
    run, the other is the one worth interrupting somebody for.
    """
    target = path if path is not None else settings_path()
    try:
        with target.open("rb") as handle:
            document = tomllib.load(handle)
    except FileNotFoundError:
        # The normal first run. Nothing was discarded, because there was nothing to discard.
        return SettingsFile(Settings())
    except OSError as error:
        return SettingsFile(Settings(), SettingsProblem(target, f"{type(error).__name__}: {error}"))
    except tomllib.TOMLDecodeError as error:
        # `tomllib`'s message carries the line and column, which is the whole value of reporting.
        return SettingsFile(Settings(), SettingsProblem(target, str(error)))
    except UnicodeDecodeError as error:
        # **Decoding fails before parsing can** (`T102-R1`). `tomllib.load` reads bytes and decodes
        # them as UTF-8 first, so a file saved in another encoding — or a truncated multi-byte
        # sequence from a partial write — raises here and never reaches the TOML parser. It is not
        # a `TOMLDecodeError` and not an `OSError`, so it escaped both branches and **aborted
        # composition**: an existing unusable settings file stopped the application starting, which
        # is the opposite of what `ARC-008` and this function's never-raises contract promise.
        #
        # Reported like any other unusable existing file, keeping the codec and the byte offset —
        # they are what tells somebody which editor wrote it and where to look.
        return SettingsFile(
            Settings(),
            SettingsProblem(
                target,
                f"The file is not valid UTF-8: {error.reason} at byte {error.start}.",
            ),
        )

    table = document.get(_TABLE)
    if table is None:
        # Parsed, and says nothing about the queue. Same promise as a deleted line.
        return SettingsFile(Settings())
    if not isinstance(table, dict):
        return SettingsFile(
            Settings(),
            SettingsProblem(
                target,
                f"The [{_TABLE}] section is a {type(table).__name__}, not a section.",
            ),
        )
    if _CONCURRENCY_KEY not in table:
        return SettingsFile(Settings())

    raw = table[_CONCURRENCY_KEY]
    if isinstance(raw, bool) or not isinstance(raw, int):
        return SettingsFile(
            Settings(),
            SettingsProblem(
                target,
                f"{_TABLE}.{_CONCURRENCY_KEY} is {raw!r}, which is not a whole number.",
            ),
        )
    return SettingsFile(Settings(concurrency=_concurrency_from(raw)))


def save(settings: Settings, path: Path | None = None) -> None:
    """Write `settings` to `path`. **Never raises** — `save_geometry`'s rule, for its reason.

    Hand-formatted rather than serialised, because this project has no TOML *writer*: `tomllib` is
    read-only in the standard library, and `window.toml` is written the same way. Adding a
    dependency to emit four lines would be a decision (`ARC-001`), not part of `T-078`.

    The comment header is for the person who opens the file, which is the point of the format
    (`DAT-001`) and — until Phase 4's dialog — one of only two ways to change this value.
    """
    target = path if path is not None else settings_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "# Tracks & Trails settings.\n"
            "# Safe to delete: every value falls back to its default.\n"
            f"[{_TABLE}]\n"
            f"# How many downloads run at once. Minimum {CONCURRENCY_MINIMUM}, "
            f"maximum {CONCURRENCY_MAXIMUM}, default {CONCURRENCY_DEFAULT}.\n"
            "# Each one is a separate worker process, so a higher number is not always faster.\n"
            f"{_CONCURRENCY_KEY} = {settings.concurrency}\n",
            encoding="utf-8",
        )
    except OSError:
        return


def with_concurrency(settings: Settings, limit: int) -> Settings:
    """`settings` with `concurrency` set to `limit`, bounded at both ends.

    A named function rather than `replace()` at each call site, so the bounds apply wherever the
    value changes and not only where it is read. A control handing over `0` gets the minimum and one
    handing over `40` gets the maximum — the same answers `load()` gives a file saying either.
    """
    return replace(settings, concurrency=min(max(limit, CONCURRENCY_MINIMUM), CONCURRENCY_MAXIMUM))
