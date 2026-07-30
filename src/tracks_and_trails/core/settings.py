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

## Reading never fails

A missing file is the normal first run. An unparseable one is a hand-edit that went wrong, a partial
write, or a file from a future version. None of those is a reason the application cannot start, so
`load()` answers with defaults and `save()` swallows `OSError` — the same rule
`ui/main_window.py.save_geometry` follows for `window.toml`, and for the same reason: a read-only
config directory is a real deployment state.

**What that gives up, stated:** a corrupt file is silently replaced by defaults rather than
reported. Nothing in `REQ-023` or `ARC-007` asks for a settings-parse diagnostic, and there is
nowhere to show one until Phase 4's dialog exists.
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


def _concurrency_from(raw: Any) -> int:
    """Coerce a value read from TOML into a usable limit. **Never raises.**

    Three outcomes, each deliberate and each named by `T-078`'s acceptance criteria:

    - **A valid integer** is used as written.
    - **An integer below the minimum** — `0`, a negative — is raised to `CONCURRENCY_MINIMUM` rather
      than replaced by the default. The user wrote a number whose evident intent is "as few as
      possible"; honouring that up to the bound respects the edit, where falling back to 3 discards
      it.
    - **Anything that is not an integer** — a string, a float, a boolean, a table — becomes
      `CONCURRENCY_DEFAULT`. There is no intent to honour: `"three"` and `2.5` do not say how many
      processes to run.

    `bool` is excluded explicitly because it is an `int` subclass, so `concurrency = true` would
    otherwise pass as `1`. Same trap `downloader/worker.py._int_or_none` avoids.

    **No maximum is applied, and that is a hole `REQ-013` leaves.** It says *bounded* and
    *minimum 1* and names no ceiling, so this module does not invent one — but a hand-edited
    `concurrency = 10000` asks the pool for ten thousand worker processes. Flagged rather than
    silently bounded: inventing a requirement is worse than naming the gap.
    """
    if isinstance(raw, bool) or not isinstance(raw, int):
        return CONCURRENCY_DEFAULT
    return max(raw, CONCURRENCY_MINIMUM)


def load(path: Path | None = None) -> Settings:
    """Read settings from `path`. **Never raises**; unreadable or invalid means defaults.

    A missing file is the normal first run, and `tomllib` raising on a malformed one says the file
    is wrong rather than that the application is. Both answer with `Settings()`.
    """
    target = path if path is not None else settings_path()
    try:
        with target.open("rb") as handle:
            document = tomllib.load(handle)
    except OSError, tomllib.TOMLDecodeError:
        return Settings()

    table = document.get(_TABLE)
    if not isinstance(table, dict) or _CONCURRENCY_KEY not in table:
        # A file holding the key at the top level, or a string where the table belongs, is not a
        # partial success. Nothing in it is trusted.
        return Settings()
    return Settings(concurrency=_concurrency_from(table[_CONCURRENCY_KEY]))


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
            f"default {CONCURRENCY_DEFAULT}.\n"
            f"{_CONCURRENCY_KEY} = {settings.concurrency}\n",
            encoding="utf-8",
        )
    except OSError:
        return


def with_concurrency(settings: Settings, limit: int) -> Settings:
    """`settings` with `concurrency` set to `limit`, bounded by `REQ-013`'s minimum.

    A named function rather than `replace()` at each call site, so the bound applies wherever the
    value changes and not only where it is read. A control handing over `0` gets the minimum — the
    same answer `load()` gives a file that says `0`.
    """
    return replace(settings, concurrency=max(limit, CONCURRENCY_MINIMUM))
