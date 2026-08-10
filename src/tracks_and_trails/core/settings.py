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

import os
import tomllib
from contextlib import suppress
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any, Final

from platformdirs import user_config_dir

from tracks_and_trails.core.models import AudioCodec, MediaKind, Preset

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

#: `T-146`'s two keys, as **sibling tables** rather than more `[queue]` members — the shape
#: `_TABLE`'s note above promised. Neither is a queue setting: one says where files land and one
#: says what the window looks like.
_DOWNLOADS_TABLE: Final = "downloads"
_DIRECTORY_KEY: Final = "directory"
_APPEARANCE_TABLE: Final = "appearance"
_THEME_KEY: Final = "theme"

#: `T-199`'s key: where ffmpeg is, when it is not on `PATH` (`REQ-023`, `REQ-024`, `OPS-001`).
#: Its own table for `[downloads]`'s reason — it is not a queue setting, and `find_ffmpeg` already
#: takes an override, so this is the setting that supplies one.
_FFMPEG_TABLE: Final = "ffmpeg"
_LOCATION_KEY: Final = "location"

#: What a chosen file's name must contain to be taken for ffmpeg (`T-199`).
#:
#: Substring rather than equality, so `ffmpeg-7`, `ffmpeg.exe` and `ffmpeg_static` are all accepted
#: — the check exists to catch a wrong file picked out of a dialog, not to police naming.
FFMPEG_NAME: Final = "ffmpeg"

#: The themes a settings file may name (`REQ-023`, `ARCHITECTURE.md` §8).
#:
#: **Named here rather than read from `ui/theme.py`**, which owns the palettes: `core/**` may not
#: import Qt (`AGENTS.md` §7), and `ui.theme` reaches Qt for `QPalette`. So this is a second place
#: the names appear, and a second place is a place to drift —
#: `tests/unit/test_theme.py` holds the one assertion that binds them, in the layer where
#: importing both is allowed.
#:
#: **Following the OS theme is deliberately not a third name.** `T-146` puts it out of scope: it
#: is a third state rather than a third palette, and it needs its own decision.
THEME_NAMES: Final = ("light", "dark")
THEME_DEFAULT: Final = "light"

#: The array-of-tables a user's saved presets live in (`DAT-001`, `T109-R5`).
#:
#: **This file, and no other** — `T-111`'s entry records it as already decided: *"User presets
#: persist as TOML in the existing `settings.toml`, per `DAT-001` and `ARCHITECTURE.md` §5. No new
#: store, no sibling file, no table, and no migration is owed."* An array of tables rather than one
#: table per name, because a preset's name is user text and a TOML key is not the place for it.
_PRESET_TABLE: Final = "preset"

#: The `Preset` fields a saved preset carries. Derived from the dataclass rather than listed, for
#: `_REQUEST_FIELDS`' reason: a field added to `Preset` and forgotten here would be silently
#: dropped on every save, and the round-trip test compares whole objects.
#:
#: `built_in` is excluded and is the one field that must be: everything in this file is the user's,
#: and a hand-edited `built_in = true` would let a saved preset claim to ship with the application.
_PRESET_FIELDS: Final = tuple(field.name for field in fields(Preset) if field.name != "built_in")

#: The name of the preset a newly pasted URL inherits (`REQ-007`, `P-7`, `UX-007`).
#:
#: **A top-level key, not a member of `[queue]` or of `[[preset]]`.** It is not a queue setting, and
#: it cannot live inside a preset table because the default may name a *built-in* — which has no
#: table in this file at all. TOML requires bare keys to precede the first table, so `save()` writes
#: it above `[queue]`, which is also where a reader looks for it first.
#:
#: **A name rather than an index or a copy.** An index would silently re-point at a different preset
#: when one earlier in the list is deleted, and a copy would be a second answer to what the preset
#: contains — the bug `REQ-009` exists to prevent. A name that resolves to nothing is handled by
#: `default_preset_of`, which is total.
_DEFAULT_PRESET_KEY: Final = "default_preset"


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

    #: The presets the user saved, in the order they were saved (`REQ-007`, `T109-R5`).
    #:
    #: **Create only, so far, and the rest is `T-111`'s.** `P-4` requires the options editor to
    #: offer *Save as preset…* explicitly, which needs somewhere to save to; editing, duplicating,
    #: deleting and choosing a default are `T-111`'s five operations built on this. Storing them
    #: here rather than in a store of their own is `T-111`'s entry's own ruling, not a choice made
    #: by `T-109`.
    presets: tuple[Preset, ...] = ()

    #: The name of the preset a new paste inherits (`REQ-007`, `P-7` ruled by `UX-007`).
    #:
    #: **Empty means "the registry's first", not "no default".** `P-7` requires that there is always
    #: exactly one default, because the dialog needs *something* to inherit — so this field is a
    #: stored *preference*, and `default_preset_of` is the function that turns it into a preset.
    #: Storing `BUILT_IN_PRESETS[0].name` here instead would freeze today's registry into every
    #: settings file ever written, so that a user who never chose a default would keep inheriting a
    #: preset this application had since replaced.
    #:
    #: May name a built-in or one of `presets`. Nothing here checks that it names anything: a file
    #: is hand-editable, a preset can be deleted, and the resolver answers in every case.
    default_preset: str = ""

    #: Where downloads are written, or `None` for the platform's own downloads directory
    #: (`REQ-023`, `T-146`). `app.default_output_directory` is what `None` resolves to, and its
    #: docstring called itself the placeholder "until `core/settings.py` lets the user say
    #: otherwise" — this field is the otherwise.
    #:
    #: **`None` rather than the resolved default**, for `default_preset`'s reason one field up:
    #: storing today's platform answer would freeze it into the file, so a user who never chose a
    #: directory would keep the answer their first launch happened to compute.
    download_directory: Path | None = None

    #: Which palette the window wears (`REQ-023`, `ARCHITECTURE.md` §8, `T-146`). One of
    #: `THEME_NAMES`; `load()` refuses anything else, so this is always a name `ui/theme.py` knows.
    theme: str = THEME_DEFAULT

    #: Where ffmpeg is, or `None` to search `PATH` (`REQ-023`, `REQ-024`, `T-199`).
    #:
    #: **Validated as a file that exists, no further** — `find_ffmpeg` decides usability, because
    #: it already applies the platform's own executable-discovery semantics (`shutil.which` on a
    #: concrete path: `X_OK` on POSIX, `PATHEXT` on Windows) and this module may not. Two places
    #: deciding whether a binary can run is two answers that can disagree.
    ffmpeg_location: Path | None = None

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
        if not isinstance(self.default_preset, str):
            raise TypeError(
                "Settings.default_preset must be a preset name, not a "
                f"{type(self.default_preset).__name__}"
            )
        if any(preset.built_in for preset in self.presets):
            raise ValueError(
                "a saved preset cannot be built_in: everything in settings.toml is the user's, "
                "and a preset claiming otherwise would be indistinguishable from one that ships "
                "with the application"
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


def _directory_from(raw: Any) -> tuple[Path | None, str | None]:
    """Coerce a stored download directory into one that can be written to. **Never raises.**

    **The substantive design question `T-146` names**, in its own words: *"a path has no equivalent
    clamp"*. `concurrency` can be pulled into range because a number out of range still says how
    many; a directory that is gone says nothing that can be repaired. So the answers differ by
    what the value can still mean:

    | The value | Answer | Reported |
    |---|---|---|
    | Absent, or an empty string | the platform default | **No** — as for any deleted line |
    | Not a string | the platform default | **Yes** — a table or a number names no directory |
    | A path that does not exist | the platform default | **Yes** |
    | A path that is not a directory | the platform default | **Yes** |
    | A directory that cannot be written to | the platform default | **Yes** |
    | A usable directory | itself | **No** |

    **A missing directory is reported rather than created**, which is the difference between this
    and composition's `mkdir` on the default. The default is a path this application chose and may
    make; a stored one is a path the *user* chose from a picker that only offers directories that
    exist, so its absence means it was deleted or its drive is not mounted. Recreating an empty
    folder where their files used to be would answer a question nobody asked, and would hide the
    unmounted drive that is the likelier cause (`ARC-008` reports rather than reverting silently).

    **Writability is asked with `os.access`, and that is not a guarantee.** On Windows it consults
    the read-only attribute rather than the ACL, so a directory it calls writable can still refuse
    a file. This is a check for the ordinary broken cases — a read-only mount, someone else's
    folder — and the download's own error path stays the authority on whether a write succeeds
    (`NFR-006` carries the message either way). Claiming more would be the kind of over-promise
    `AGENTS.md` §7 forbids.
    """
    if raw is None:
        return None, None
    if not isinstance(raw, str):
        return None, (
            f"{_DOWNLOADS_TABLE}.{_DIRECTORY_KEY} is {raw!r}, which is not a path. "
            "Downloads will go to the default folder."
        )
    if not raw.strip():
        # Deliberately silent: an empty value is how a user says "use the default" without
        # deleting the line, and `save()`'s header promises deleting it is safe.
        return None, None

    try:
        # **Inside the guard, because expanding a `~` is itself a lookup that fails** (`T146-R1`).
        # `~someone-who-left/downloads` raises `RuntimeError` when the account cannot be resolved
        # — no home directory to expand to — and this call sat *above* the try, so the error left
        # `load()`, broke its never-raises contract, and stopped the application starting on a
        # settings file it was supposed to report. Exactly the shape `T102-R1` found in decoding,
        # in the branch written to remember it.
        candidate = Path(raw).expanduser()
        if not candidate.exists():
            return None, (
                f"The download folder in your settings no longer exists, so downloads will go to "
                f"the default folder instead.\n{candidate}"
            )
        if not candidate.is_dir():
            return None, (
                f"The download folder in your settings is a file, not a folder, so downloads "
                f"will go to the default folder instead.\n{candidate}"
            )
        if not os.access(candidate, os.W_OK):
            return None, (
                f"The download folder in your settings cannot be written to, so downloads will "
                f"go to the default folder instead.\n{candidate}"
            )
    except (OSError, RuntimeError) as error:
        # **This function's never-raises contract, kept against the filesystem** — the same lesson
        # `T102-R1` taught about decoding: a check that can raise is a check that can stop the
        # application starting, which is the opposite of what `ARC-008` promises. A path on a
        # disconnected network share raises `OSError` here rather than answering False.
        #
        # **`RuntimeError` is `expanduser`'s** answer for a `~user` it cannot resolve, which is
        # `T146-R1` (`ValueError` was in this tuple for one draft, for a path holding a NUL byte —
        # removed because it cannot happen *here*: `tomllib` rejects a raw NUL while parsing, so
        # such a value is reported as a decode error and never reaches this function. A caught
        # exception nobody can produce is a claim, not a guard.)
        #
        # The reported text names the value **as written** rather than the expansion, because when
        # the expansion is what failed there is no expanded path to name.
        return None, (
            f"The download folder in your settings could not be checked, so downloads will go to "
            f"the default folder instead.\n{raw}\n{type(error).__name__}: {error}"
        )
    return candidate, None


def _ffmpeg_location_from(raw: Any) -> tuple[Path | None, str | None]:
    """Coerce a stored ffmpeg location. **Never raises**, and reports what it discards.

    The same three-way split `_directory_from` uses, and the same reason each answer differs:
    absent or empty is silent, because clearing the box is how a user asks for `PATH` again;
    anything else that cannot be used is **reported** under `ARC-008`, because a setting that
    silently did nothing is what `T-109` and `T-113` were both Criticals about — a path this
    application did not choose, trusted without checking.

    **Existence is the whole check here.** Whether the file can actually be executed is
    `find_ffmpeg`'s answer, and it is deliberately not second-guessed: it applies the platform's
    own rules, and a second opinion in this module would be a third behaviour to keep in step.
    The application still starts either way — an unusable location resolves to no ffmpeg, and
    `REQ-024` makes that a loss of features rather than a failure to run.
    """
    if raw is None:
        return None, None
    if not isinstance(raw, str):
        return None, (
            f"{_FFMPEG_TABLE}.{_LOCATION_KEY} is {raw!r}, which is not a path. ffmpeg will be "
            "looked for on PATH."
        )
    if not raw.strip():
        return None, None

    try:
        candidate = Path(raw).expanduser()
        if not candidate.exists():
            return None, (
                f"The ffmpeg location in your settings does not exist, so ffmpeg will be looked "
                f"for on PATH instead.\n{candidate}"
            )
        if not candidate.is_file():
            return None, (
                f"The ffmpeg location in your settings is not a file, so ffmpeg will be looked "
                f"for on PATH instead.\n{candidate}"
            )
        if FFMPEG_NAME not in candidate.name.lower():
            # **A name check, and it does not pretend to be more** (`T-199`). Nothing here runs
            # the file to ask what it is: this module never executes anything, and `find_ffmpeg`
            # gives the same reason — running an unknown binary is a larger surface than the
            # question needs. So this catches the realistic mistake, which is picking the wrong
            # file out of a dialog, and not a renamed impostor. `ffmpeg-7`, `ffmpeg.exe` and
            # `ffmpeg_static` all pass, because rejecting a legitimately-named build would cost a
            # real user more than the check is worth.
            return None, (
                f"The ffmpeg location in your settings does not look like ffmpeg, so ffmpeg will "
                f"be looked for on PATH instead.\n{candidate}"
            )
    except (OSError, RuntimeError) as error:
        # `T146-R1`'s lesson, applied where the same shapes arrive: expansion and the filesystem
        # both raise, and `load()` promises it never does.
        return None, (
            f"The ffmpeg location in your settings could not be checked, so ffmpeg will be looked "
            f"for on PATH instead.\n{raw}\n{type(error).__name__}: {error}"
        )
    return candidate, None


def _theme_from(raw: Any) -> tuple[str, str | None]:
    """Coerce a stored theme name. **Never raises.**

    Unknown names are reported rather than clamped for `_directory_from`'s reason: `"solarized"`
    expresses a preference this application cannot honour, and picking the nearest of two would be
    inventing an answer. Absent is silent, as every omission here is.
    """
    if raw is None:
        return THEME_DEFAULT, None
    if not isinstance(raw, str) or raw not in THEME_NAMES:
        return THEME_DEFAULT, (
            f"{_APPEARANCE_TABLE}.{_THEME_KEY} is {raw!r}, which is not one of "
            f"{', '.join(THEME_NAMES)}. The {THEME_DEFAULT} theme is in use."
        )
    return raw, None


def _section_of(document: dict[str, Any], table: str) -> tuple[dict[str, Any], str | None]:
    """One optional table, or an empty one and a reason it could not be read."""
    section = document.get(table)
    if section is None:
        return {}, None
    if not isinstance(section, dict):
        return {}, f"The [{table}] section is a {type(section).__name__}, not a section."
    return section, None


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
    | Parses, a `[[preset]]` entry is malformed | **Yes** — that entry only; the rest survive |

    **The two halves are read independently** (`T109-R5`). A broken `[queue]` section must not cost
    the user their saved presets, and a typo in the tenth preset must not reset the concurrency
    limit. Both reasons are reported when both apply.

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

    # **Read independently, and reported together.** A broken `[queue]` section must not cost the
    # user their saved presets, and a preset with a typo in it must not reset the concurrency
    # limit: they are separate values in one file, and `ARC-008` asks what was *discarded*, not
    # what the file's worst part was.
    presets, preset_reason = _presets_from(document)
    default, default_reason = _default_preset_from(document, presets)

    # `T-146`'s two, read the same independent way and for the same reason: a theme name nobody
    # recognises must not cost the user their download folder.
    downloads_table, downloads_reason = _section_of(document, _DOWNLOADS_TABLE)
    directory, directory_reason = _directory_from(downloads_table.get(_DIRECTORY_KEY))
    appearance_table, appearance_reason = _section_of(document, _APPEARANCE_TABLE)
    theme, theme_reason = _theme_from(appearance_table.get(_THEME_KEY))
    ffmpeg_table, ffmpeg_reason = _section_of(document, _FFMPEG_TABLE)
    ffmpeg_location, location_reason = _ffmpeg_location_from(ffmpeg_table.get(_LOCATION_KEY))

    def answer(concurrency: int, reason: str | None = None) -> SettingsFile:
        parts = [
            part
            for part in (
                reason,
                preset_reason,
                default_reason,
                downloads_reason,
                directory_reason,
                appearance_reason,
                theme_reason,
                ffmpeg_reason,
                location_reason,
            )
            if part
        ]
        settings = Settings(
            concurrency=concurrency,
            presets=presets,
            default_preset=default,
            download_directory=directory,
            theme=theme,
            ffmpeg_location=ffmpeg_location,
        )
        if not parts:
            return SettingsFile(settings)
        return SettingsFile(settings, SettingsProblem(target, "\n\n".join(parts)))

    table = document.get(_TABLE)
    if table is None:
        # Parsed, and says nothing about the queue. Same promise as a deleted line.
        return answer(CONCURRENCY_DEFAULT)
    if not isinstance(table, dict):
        return answer(
            CONCURRENCY_DEFAULT,
            f"The [{_TABLE}] section is a {type(table).__name__}, not a section.",
        )
    if _CONCURRENCY_KEY not in table:
        return answer(CONCURRENCY_DEFAULT)

    raw = table[_CONCURRENCY_KEY]
    if isinstance(raw, bool) or not isinstance(raw, int):
        return answer(
            CONCURRENCY_DEFAULT,
            f"{_TABLE}.{_CONCURRENCY_KEY} is {raw!r}, which is not a whole number.",
        )
    return answer(_concurrency_from(raw))


def _preset_from(raw: Any) -> Preset:
    """One `[[preset]]` table as a `Preset`. **Raises** for anything the model would refuse.

    Every value is handed to `Preset`, which validates it — a name that is not text, a container
    yt-dlp does not accept, a remux *and* a recode together. Re-checking here would be a second
    opinion about what a preset may be, and the model is the one that has to be right because the
    download reads it.

    Enums are rebuilt from their values rather than cast, because TOML has none. An unknown codec
    or media kind raises `ValueError` from the enum itself, which is what the caller reports.
    """
    if not isinstance(raw, dict):
        raise TypeError(f"a preset must be a table, not a {type(raw).__name__}")
    unknown = sorted(set(raw) - set(_PRESET_FIELDS))
    if unknown:
        # Named rather than ignored: a key this version does not know is either a typo the user
        # wants to hear about or a field from a future version, and silently dropping it would
        # write the file back without it.
        raise ValueError(f"unknown key(s) {', '.join(unknown)}")
    values = dict(raw)
    if "media_kind" in values:
        values["media_kind"] = MediaKind(values["media_kind"])
    if "audio_codec" in values:
        values["audio_codec"] = AudioCodec(values["audio_codec"])
    for name in ("post_processors", "subtitle_languages"):
        if name in values:
            values[name] = tuple(values[name])
    return Preset(**values, built_in=False)


def _presets_from(document: dict[str, Any]) -> tuple[tuple[Preset, ...], str | None]:
    """Every readable saved preset, and what had to be discarded to get them (`ARC-008`).

    **A bad entry is dropped and reported; the good ones survive.** The alternative — discarding
    every preset because one is malformed — punishes a user for a typo in the tenth of ten, and
    `ARC-008`'s rule is that something discarded is *reported*, not that everything is.

    **A name already spoken for is as unreadable as a malformed entry** (`T111-R2`). This checked
    each entry's *shape* and nothing about its name, so a hand-edited file naming a preset
    `Audio only (MP3)` loaded clean: two rows of that name in the manager, `problem=None`, and
    `preset_named` answering with the built-in while the saved row held a different selector. Every
    operation this module offers addresses a preset **by name** — `preset_named`, `update_preset`,
    `remove_preset`, `set_default_preset` — so a duplicate name is not untidy, it is a row the code
    cannot address correctly, and `REQ-009`'s promise that the name names the download fails with
    it.

    **Refused rather than disambiguated, which is the stated policy applied and not a new one.**
    `add_preset` refuses a name the *user typed* and `free_preset_name` disambiguates one *nobody
    proposed*; a name in a hand-edited file is the first of those, typed in an editor instead of a
    dialog. Renaming it here would also be this module quietly editing a file the user wrote by
    hand — the thing `ARC-008` exists to report rather than do.

    **Built-ins are in the check and are checked first**, so a saved entry cannot shadow one that
    ships; earlier entries win over later ones, so the file's own order decides and the answer does
    not depend on `dict` iteration or on which duplicate was written last.
    """
    entries = document.get(_PRESET_TABLE)
    if entries is None:
        return (), None
    if not isinstance(entries, list):
        return (), f"[[{_PRESET_TABLE}]] is a {type(entries).__name__}, not a list of presets."

    from tracks_and_trails.core.presets import BUILT_IN_PRESETS

    kept: list[Preset] = []
    refused: list[str] = []
    taken = {preset.name for preset in BUILT_IN_PRESETS}
    for position, entry in enumerate(entries):
        named = entry.get("name") if isinstance(entry, dict) else None
        which = f"{named!r}" if isinstance(named, str) else f"number {position + 1}"
        try:
            preset = _preset_from(entry)
        except (TypeError, ValueError) as error:
            refused.append(f"preset {which}: {error}")
            continue
        if preset.name in taken:
            refused.append(
                f"preset {which}: a preset called {preset.name!r} already exists, and every "
                "operation addresses a preset by name"
            )
            continue
        taken.add(preset.name)
        kept.append(preset)
    if not refused:
        return tuple(kept), None
    return tuple(kept), (
        f"{len(refused)} saved preset(s) could not be read and were left out:\n"
        + "\n".join(refused)
    )


def _default_preset_from(
    document: dict[str, Any], presets: tuple[Preset, ...]
) -> tuple[str, str | None]:
    """The stored default preset name, and what had to be discarded to get it (`ARC-008`).

    Read as its own value, like `[queue]` and `[[preset]]` before it: a default naming a preset that
    is not there must not cost the user their presets, and a preset that failed to parse must not go
    unreported because the default was fine.

    **A name that resolves to nothing is reported, not silently corrected.** `default_preset_of`
    already answers with the registry's first, so the application works either way — but the user's
    stored choice *was* discarded, and `ARC-008`'s rule is that a discard is reported. The commonest
    way to reach this is the one worth naming: a preset earlier in the same file was malformed, was
    dropped, and was the default.

    Omission stays silent, for the reason `save()`'s header promises: every value falls back to its
    default, and a deleted line is not a broken file.
    """
    raw = document.get(_DEFAULT_PRESET_KEY)
    if raw is None:
        return "", None
    if not isinstance(raw, str):
        return "", f"{_DEFAULT_PRESET_KEY} is {raw!r}, which is not a preset name."

    from tracks_and_trails.core.presets import BUILT_IN_PRESETS

    if any(preset.name == raw for preset in (*BUILT_IN_PRESETS, *presets)):
        return raw, None
    return "", (
        f"{_DEFAULT_PRESET_KEY} is {raw!r}, and no preset of that name exists. "
        "A new download will inherit the first built-in preset instead."
    )


def _toml_string(value: str) -> str:
    """`value` as a TOML basic string. **Total for every string** (`T109-R9`).

    Hand-written because this project has no TOML *writer* — `tomllib` is read-only in the standard
    library, and `save()` and `window.toml` are both hand-formatted for that reason. A preset name
    is user text, so the escaping is not optional: a name containing a quote or a backslash would
    otherwise produce a file this module cannot read back, which is the round trip breaking itself.

    **Every control character, not the five that were thought of.** A `QLineEdit` keeps whatever is
    pasted into it, and TOML forbids a raw control character in a basic string — so a name carrying
    `\x08` produced a file `tomllib` refused, and the *next* `load()` therefore returned no presets
    and reset the concurrency limit to its default. One bad character in one name destroyed
    unrelated settings. Escaping by codepoint is total: there is no input this cannot represent,
    which is a stronger property than a longer list of special cases.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + "".join(_toml_character(character) for character in escaped) + '"'


def _toml_character(character: str) -> str:
    """One character, escaped where TOML requires it.

    `\\uXXXX` for anything below `0x20` and for `DEL`, which is what TOML's own grammar allows and
    what `tomllib` reads back. The three named escapes are spelled for legibility — a newline in a
    preset name is odd, and `\\n` in the file says so more clearly than `\\u000A`.
    """
    named = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}
    if character in named:
        return named[character]
    if ord(character) < 0x20 or ord(character) == 0x7F:
        return f"\\u{ord(character):04X}"
    return character


def _toml_value(value: Any) -> str:
    """One preset field, rendered. Only the shapes `Preset` can hold are handled."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, tuple | list):
        return "[" + ", ".join(_toml_string(str(item)) for item in value) + "]"
    return _toml_string(str(value))


def _preset_lines(preset: Preset) -> str:
    """One `[[preset]]` table. `None` fields are omitted, because TOML has no null."""
    lines = [f"\n[[{_PRESET_TABLE}]]"]
    for name in _PRESET_FIELDS:
        value = getattr(preset, name)
        if value is None:
            continue
        lines.append(f"{name} = {_toml_value(value)}")
    return "\n".join(lines) + "\n"


def add_preset(settings: Settings, preset: Preset) -> Settings:
    """`settings` with `preset` saved. **The creation half of `REQ-007`** (`P-4`, `T109-R5`).

    `T-111` owns edit, duplicate, delete and set-default; this is the seam they build on, and it
    exists now because `P-4` requires the options editor to offer *Save as preset…* and a control
    with nowhere to save to is one `UX-005` §5 forbids drawing.

    **A colliding name is refused, and refused loudly.** `REQ-009`'s promise is that the name names
    the download, and the staging list decides *"this row already has that format"* by comparing
    names (`T-159`) — so two presets sharing one would make a row's choice ambiguous to the code as
    well as to the reader. Built-ins are included in the check: a saved preset called *Audio only
    (MP3)* would shadow the one that ships.

    Raises `ValueError` rather than disambiguating silently. The caller is an editor with the user
    in front of it and can ask for another name; picking one for them is how *Audio only (MP3) (2)*
    appears in a list nobody meant to create.
    """
    if preset.built_in:
        raise ValueError("a built-in preset is not the user's to save")
    if preset.name in _taken_names(settings):
        raise ValueError(f"a preset called {preset.name!r} already exists")
    return replace(settings, presets=(*settings.presets, preset))


def _taken_names(settings: Settings) -> set[str]:
    """Every preset name that is spoken for, built-in and saved alike.

    Imported inside the function, as `add_preset` did before these five operations shared it:
    `core.presets` is the registry this module stores *around*, and a module-level import would
    make the settings layer and the preset registry one import cycle apart for no gain.
    """
    from tracks_and_trails.core.presets import BUILT_IN_PRESETS

    return {existing.name for existing in (*BUILT_IN_PRESETS, *settings.presets)}


def all_presets(settings: Settings) -> tuple[Preset, ...]:
    """**One list**, built-ins first and the user's after (`P-6`, ruled by `UX-007`).

    The manager shows a single list rather than two, and the dialog offers the same sequence, so
    both read it from here instead of concatenating it themselves — two concatenations would be two
    orders the moment one of them was edited.
    """
    from tracks_and_trails.core.presets import BUILT_IN_PRESETS

    return (*BUILT_IN_PRESETS, *settings.presets)


def preset_named(settings: Settings, name: str) -> Preset | None:
    """The preset called `name`, built-in or saved, or `None`.

    `None` rather than `KeyError` because every caller here is asking a question about user input —
    a name typed into a form, a name read from a hand-edited file — where absence is an ordinary
    answer. `presets.by_name` keeps raising, for the different question it answers.
    """
    return next((preset for preset in all_presets(settings) if preset.name == name), None)


def default_preset_of(settings: Settings) -> Preset:
    """The preset a new paste inherits. **Total: there is always exactly one** (`P-7`, `UX-007`).

    Three ways the stored name can fail to name a preset, and all three answer the same way — the
    first built-in, which is the registry's own first offer:

    - nothing was ever chosen, which is every first run;
    - the preset it named was deleted, and `remove_preset` clears the field for exactly this reason;
    - the file was hand-edited to a name that does not exist.

    Falling back rather than raising is what makes `P-7` true. *"Always exactly one default, always
    set"* is a promise the dialog relies on to have something to inherit, and a resolver that could
    raise would move the problem into the paste path instead of solving it.
    """
    from tracks_and_trails.core.presets import BUILT_IN_PRESETS

    chosen = preset_named(settings, settings.default_preset) if settings.default_preset else None
    return chosen if chosen is not None else BUILT_IN_PRESETS[0]


def set_default_preset(settings: Settings, name: str) -> Settings:
    """`settings` with `name` as the preset a new paste inherits (`REQ-007`'s fifth verb).

    **A built-in may be the default, and clearing it is not offered** (`P-7`). The five verbs are
    create, edit, duplicate, delete and *set default* — there is no *unset*, because the dialog
    needs something to inherit and `default_preset_of` would answer with the registry's first
    anyway. A caller wanting that writes the built-in's name.

    Raises for a name that names nothing: the caller is a list the user selected a row in, so an
    unknown name is a programming error rather than a preference to honour.
    """
    if preset_named(settings, name) is None:
        raise ValueError(f"no preset called {name!r}")
    return replace(settings, default_preset=name)


def update_preset(settings: Settings, name: str, preset: Preset) -> Settings:
    """`settings` with the saved preset called `name` replaced by `preset`. **Edit**, of the five.

    **A built-in is refused here rather than disabled in the widget** (`REQ-006`). Editing one in
    place would leave a preset whose contents no longer match the name it ships under, which is
    `REQ-009`'s promise broken at the source; `docs/UX_SPEC.md` §8 makes duplicating it the way to
    start from one, and `duplicate_preset` is that route.

    **The position is kept**, so editing a preset does not move it to the end of the user's own
    list. The list is in the order they were saved, and an edit is not a save.

    **A rename carries the default with it.** The default is stored as a name, so renaming the
    preset that holds it would otherwise leave the field naming nothing and silently hand the user
    back the registry's first preset — a deletion's behaviour for what was only an edit.
    """
    if preset.built_in:
        raise ValueError("a saved preset cannot be built_in")
    index = next(
        (position for position, saved in enumerate(settings.presets) if saved.name == name), None
    )
    if index is None:
        from tracks_and_trails.core.presets import BUILT_IN_PRESETS

        if any(built_in.name == name for built_in in BUILT_IN_PRESETS):
            raise ValueError(
                f"{name!r} is a built-in preset and cannot be edited; duplicate it to start from it"
            )
        raise ValueError(f"no saved preset called {name!r}")
    if preset.name != name and preset.name in _taken_names(settings):
        raise ValueError(f"a preset called {preset.name!r} already exists")

    saved = (*settings.presets[:index], preset, *settings.presets[index + 1 :])
    default = preset.name if settings.default_preset == name else settings.default_preset
    return replace(settings, presets=saved, default_preset=default)


def remove_preset(settings: Settings, name: str) -> Settings:
    """`settings` without the saved preset called `name`. **Delete**, of the five.

    **Deleting the default leaves a defined default**, which is this task's own acceptance
    criterion and `P-7`'s requirement. The field is cleared rather than re-pointed at a neighbour:
    `default_preset_of` then answers with the registry's first, which is a defined answer the user
    can predict, where "whichever preset happened to be next in the list" is not.
    """
    if not any(saved.name == name for saved in settings.presets):
        from tracks_and_trails.core.presets import BUILT_IN_PRESETS

        if any(built_in.name == name for built_in in BUILT_IN_PRESETS):
            raise ValueError(f"{name!r} is a built-in preset and cannot be deleted")
        raise ValueError(f"no saved preset called {name!r}")

    saved = tuple(preset for preset in settings.presets if preset.name != name)
    default = "" if settings.default_preset == name else settings.default_preset
    return replace(settings, presets=saved, default_preset=default)


def free_preset_name(settings: Settings, base: str) -> str:
    """`base`, or the first `base (copy)` / `base (copy 2)` … that nothing is called yet.

    **This is not `add_preset` disambiguating**, which it still refuses to do. The difference is who
    proposed the name: a user who typed one is asked for another, because picking for them is how
    *Audio only (MP3) (2)* appears in a list nobody meant to create. Duplication proposes no name at
    all, so there is nothing to refuse — and the proposal lands in the form, where it is edited
    before it is saved.
    """
    taken = _taken_names(settings)
    if base not in taken:
        return base
    candidate = f"{base} (copy)"
    counter = 2
    while candidate in taken:
        candidate = f"{base} (copy {counter})"
        counter += 1
    return candidate


def duplicate_preset(settings: Settings, name: str) -> tuple[Settings, Preset]:
    """`settings` with a copy of `name` saved under a free name, and the copy itself.

    **Built-ins are duplicable and that is the point** (`docs/UX_SPEC.md` §8): a built-in cannot be
    edited, so duplicating it is how a user starts from one. The copy is the user's — `built_in` is
    dropped, which `Settings` would refuse to store anyway.

    Returns the copy as well as the settings so the caller can select it. Finding it again by name
    would work and would be a second place that knows how `free_preset_name` chose.
    """
    source = preset_named(settings, name)
    if source is None:
        raise ValueError(f"no preset called {name!r}")
    copy = replace(source, name=free_preset_name(settings, name), built_in=False)
    return add_preset(settings, copy), copy


def save(settings: Settings, path: Path | None = None) -> str | None:
    """Write `settings` to `path`. **Never raises**, and **says whether it wrote** (`T109-R9`).

    Returning the failure rather than swallowing it is the correction: the policy that an
    unwritable config directory must not take the application down is unchanged, and it was never
    a reason for a *caller* to be told the write succeeded. `P-4`'s *Save as preset…* did exactly
    that — a read-only directory produced `Saved as Weekend viewing.` and no preset — because the
    only channel this function had was an exception it had promised not to raise.

    `None` means written. Existing callers that ignore the answer keep the old behaviour, which is
    right for them: the concurrency control has already applied the limit in memory and a failure
    to persist it is not worth interrupting an interaction for.

    Hand-formatted rather than serialised, because this project has no TOML *writer*: `tomllib` is
    read-only in the standard library, and `window.toml` is written the same way. Adding a
    dependency to emit four lines would be a decision (`ARC-001`), not part of `T-078`.

    The comment header is for the person who opens the file, which is the point of the format
    (`DAT-001`) and — until Phase 4's dialog — one of only two ways to change this value.
    """
    target = path if path is not None else settings_path()
    # **Written beside the file and moved onto it** (`T109-R9`). `write_text` truncates first, so a
    # write that fails partway — a full disk, a disconnected profile directory — leaves a truncated
    # file where working settings used to be, and the next `load()` reports the user's own presets
    # as unreadable. `os.replace` within one directory is atomic, so the file is either the old one
    # or the new one. The same reasoning as `claim_output_path`'s, one layer over.
    scratch = target.with_name(f"{target.name}.writing")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # **Above `[queue]` because TOML requires it.** A bare key written after the first table
        # header would belong to that table, so `default_preset` would silently become
        # `queue.default_preset` and `load()` would never find it.
        default_line = (
            f"# The preset a newly pasted URL inherits. May name a built-in.\n"
            f"{_DEFAULT_PRESET_KEY} = {_toml_string(settings.default_preset)}\n\n"
            if settings.default_preset
            else ""
        )
        # **Written after `[queue]` and before the presets, for the reader's sake only** (`T-146`).
        # A TOML table header is an absolute path from the root, so `[downloads]` after a
        # `[[preset]]` would still be a top-level table and would still round-trip — measured, by
        # mutating this order and watching the round-trip test stay green. What the order buys is
        # that the file's settings sit together above a list that grows without limit, which is
        # the point of a format `DAT-001` chose for being hand-editable.
        #
        # *(This comment claimed the order was load-bearing — that a later header would be read as
        # a member of the preceding preset. That is bare-key behaviour, not table-header
        # behaviour, and the mutation is what showed the claim up.)*
        downloads_lines = (
            f"\n\n[{_DOWNLOADS_TABLE}]\n"
            "# Where downloads are written. Delete the line for your usual downloads folder.\n"
            f"{_DIRECTORY_KEY} = {_toml_string(str(settings.download_directory))}\n"
            if settings.download_directory is not None
            else ""
        )
        ffmpeg_lines = (
            f"\n\n[{_FFMPEG_TABLE}]\n"
            "# Where ffmpeg is. Delete the line to look for it on PATH.\n"
            f"{_LOCATION_KEY} = {_toml_string(str(settings.ffmpeg_location))}\n"
            if settings.ffmpeg_location is not None
            else ""
        )
        appearance_lines = (
            f"\n\n[{_APPEARANCE_TABLE}]\n"
            f"# The window's palette: {' or '.join(THEME_NAMES)}.\n"
            f"{_THEME_KEY} = {_toml_string(settings.theme)}\n"
        )
        scratch.write_text(
            "# Tracks & Trails settings.\n"
            "# Safe to delete: every value falls back to its default.\n"
            f"{default_line}"
            f"[{_TABLE}]\n"
            f"# How many downloads run at once. Minimum {CONCURRENCY_MINIMUM}, "
            f"maximum {CONCURRENCY_MAXIMUM}, default {CONCURRENCY_DEFAULT}.\n"
            "# Each one is a separate worker process, so a higher number is not always faster.\n"
            f"{_CONCURRENCY_KEY} = {settings.concurrency}\n"
            f"{downloads_lines}"
            f"{ffmpeg_lines}"
            f"{appearance_lines}" + "".join(_preset_lines(preset) for preset in settings.presets),
            encoding="utf-8",
        )
        scratch.replace(target)
    except OSError as error:
        with suppress(OSError):
            scratch.unlink(missing_ok=True)
        return f"{type(error).__name__}: {error}"
    return None


def with_concurrency(settings: Settings, limit: int) -> Settings:
    """`settings` with `concurrency` set to `limit`, bounded at both ends.

    A named function rather than `replace()` at each call site, so the bounds apply wherever the
    value changes and not only where it is read. A control handing over `0` gets the minimum and one
    handing over `40` gets the maximum — the same answers `load()` gives a file saying either.
    """
    return replace(settings, concurrency=min(max(limit, CONCURRENCY_MINIMUM), CONCURRENCY_MAXIMUM))


def with_download_directory(settings: Settings, directory: Path | None) -> Settings:
    """`settings` with the download folder set, or cleared back to the platform's (`T-146`).

    A named function for `with_concurrency`'s reason: one place the value changes, so the meaning
    of `None` cannot be re-invented at each call site.
    """
    return replace(settings, download_directory=directory)


def with_ffmpeg_location(settings: Settings, location: Path | None) -> Settings:
    """`settings` pointing at `location`, or cleared back to `PATH` resolution (`T-199`).

    `None` is *look on `PATH`*, which is what clearing the box asks for — a named function so
    that meaning lives in one place, exactly as `with_download_directory` holds its own.
    """
    return replace(settings, ffmpeg_location=location)


def with_theme(settings: Settings, name: str) -> Settings:
    """`settings` wearing `name`, or the default if it is not a theme this application has.

    Refused rather than stored, so a caller cannot persist a name `ui/theme.py` would fail to
    resolve — the same bound-at-the-value rule `with_concurrency` applies to a number.
    """
    return replace(settings, theme=name if name in THEME_NAMES else THEME_DEFAULT)
