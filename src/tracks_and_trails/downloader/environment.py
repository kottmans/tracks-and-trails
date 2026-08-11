"""Locates yt-dlp and ffmpeg. Reports what is present; decides nothing about what works.

`ARCHITECTURE.md` §6 puts yt-dlp resolution at worker start (`OPS-002`): the user-managed copy
in `user_data_dir/tracksandtrails/ytdlp/` first, then the bundled baseline. Without that
ordering a worker imports whatever yt-dlp happens to be on `sys.path`, which is exactly what
`OPS-002` rejects — the pinned baseline stops being pinned.

## The split, and why it is drawn here

**This module locates. `worker.py` imports.**

§6 permits `import yt_dlp` in `worker.py` and `ytdlp_adapter.py` and nowhere else, and
`tests/unit/test_layering.py` enforces that after two review rounds hardening it against being
weakened. So this module cannot answer "does that copy work?" or "what version is it?" —
both require importing it. Reaching for `importlib` to slip past the guard would be worse than
an honest violation, because it defeats a check the project deliberately hardened.

What `worker.py` does with the list: walk it, prepend the first entry to `sys.path`, import,
and on `ImportError` fall back to the next — reporting which candidate it used and why any
earlier one was rejected. §6 requires failing loudly and never silently ignoring an override.
The version comes from the imported module, so only the importer can report it (`REQ-025`).

If a third module ever genuinely needs to import yt-dlp, that is an architecture change:
amend §6 and the layering rule deliberately, in a reviewed change.

## ffmpeg

Detected at startup so the user is told up front which features are unavailable (`REQ-024`),
rather than discovering it at merge time after a download has already spent their bandwidth.
`OPS-001` allows an explicit override path on both platforms.

No Qt: this runs in the worker as well as the GUI process. No shell, ever
(`ARCHITECTURE.md` §9) — `shutil.which` searches `PATH` directly.
"""

import os
import shutil
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Final

from platformdirs import user_data_dir

from tracks_and_trails.core.paths import APP_SLUG


class FfmpegFeature(Enum):
    """What stops working without ffmpeg, as a value the UI can key on (`REQ-024`, `T-199`).

    **A member rather than a sentence, because two lists that must match will drift.** These were
    four strings, and the surfaces that gate on ffmpeg matched them by nothing at all — the format
    table hid its merge mode (`P-13`) while the options dialog went on offering audio conversion,
    remuxing and embedding with ffmpeg absent. `UX-005` §5 says nothing is drawn that would be
    refused, and that was three quarters untrue.

    Now the report and the offer read the same members, and
    `tests/ui/test_options_dialog.py::test_every_ffmpeg_feature_is_withdrawn_from_the_offer`
    walks this enum: a member added here with no controls named against it fails that test rather
    than quietly becoming a feature the application offers and cannot perform.

    **This does not re-derive which features need ffmpeg** — `T-199` is explicit that this is
    `T-109`'s and `T-181`'s settled ground. The wording is carried over exactly.
    """

    MERGE = "merging separate video and audio streams"
    AUDIO = "extracting or converting audio"
    CONTAINER = "remuxing and recoding"
    EMBED = "embedding thumbnails, metadata, chapters and subtitles"


#: Features that need ffmpeg, named in the terms a user would recognise (`REQ-024`, `REQ-010`).
#:
#: Spelled out rather than "some features are unavailable": a user who is told *what* stops
#: working can decide whether they care, and one who is told nothing files a bug instead.
#:
#: Derived from `FfmpegFeature` rather than restated, so the prose and the members cannot disagree.
FFMPEG_DEPENDENT_FEATURES: Final = tuple(feature.value for feature in FfmpegFeature)


#: The pinned baseline from `pyproject.toml`, restated here so a frozen artifact can check
#: itself (`OPS-002`, `T033-R1`).
#:
#: Duplicated deliberately rather than read from `pyproject.toml` at runtime: a frozen build
#: does not ship `pyproject.toml`, and bundling it to answer one question would put build
#: metadata inside the artifact. `tests/unit/test_environment.py` asserts the two agree, so the
#: duplication cannot drift silently — which is the only thing that makes it acceptable.
BASELINE_YTDLP_VERSION: Final = "2026.7.4"


def normalise_version(version: str) -> tuple[int, ...]:
    """Compare yt-dlp versions by value rather than by spelling (`T033-R1`).

    The pin is written `2026.7.4` and the package reports `2026.07.04`. They are the same
    release, so a string comparison would fail an artifact that is in fact correct — and, worse,
    invite someone to "fix" it by loosening the check into one that passes for everything.

    Non-numeric parts sort as `-1` rather than raising: a development or patched build should
    fail the equality check loudly, not crash the probe that exists to report on it.
    """
    parts: list[int] = []
    for piece in version.strip().split("."):
        parts.append(int(piece) if piece.isdigit() else -1)
    return tuple(parts)


def user_ytdlp_directory() -> Path:
    """`user_data_dir/tracksandtrails/ytdlp/` — where a user-managed copy lives (`OPS-002`).

    `appauthor=False` is load-bearing on Windows and a no-op on Linux: platformdirs otherwise
    inserts an author segment defaulting to the app name, producing a doubled
    `tracksandtrails/tracksandtrails/` that matches none of `ARCHITECTURE.md` §5's paths. The
    same trap `T-007` hit for `window.toml`.
    """
    return Path(user_data_dir(APP_SLUG, appauthor=False)) / "ytdlp"


@dataclass(frozen=True, slots=True)
class YtdlpCandidate:
    """One place yt-dlp might be, in resolution order.

    Carries no version and no usability verdict — both need an import, which belongs to
    `worker.py`.

    There is no `exists` flag (`T035-R1`). An earlier version always returned two entries and
    marked the user copy absent, which contradicted the acceptance criterion that with no user
    copy "the candidate list contains the baseline alone" — and the test quietly weakened itself
    to "the only *present* candidate" to match. **Only real candidates are listed**, so a caller
    walking the tuple needs no filtering and cannot forget to.
    """

    #: `None` means "already importable from the environment" — the bundled baseline, or the
    #: development virtualenv. `worker.py` imports without touching `sys.path` in that case.
    path: Path | None
    source: str


def ytdlp_candidates(user_directory: Path | None = None) -> tuple[YtdlpCandidate, ...]:
    """Candidate locations in the order `worker.py` must try them (`ARCHITECTURE.md` §6).

    The user-managed copy first, then the bundled baseline. **Only candidates that exist are
    listed** (`T035-R1`), so with no user copy the tuple is the baseline alone.

    A user copy *is* listed when the directory exists but is empty or holds no `yt_dlp`
    package: deciding it unusable requires importing it, and `worker.py` owns that. Filtering
    here on a `yt_dlp/` directory check would be this module forming the verdict it may not
    form, and would be wrong for a wheel layout this code has not anticipated. The distinction
    is between "there is nothing here" — which the filesystem answers — and "what is here does
    not work", which only an import answers.
    """
    directory = user_ytdlp_directory() if user_directory is None else user_directory
    baseline = YtdlpCandidate(path=None, source="bundled baseline")
    if not directory.is_dir():
        return (baseline,)
    return (
        YtdlpCandidate(path=directory, source="user-managed copy (OPS-002)"),
        baseline,
    )


@dataclass(frozen=True, slots=True)
class FfmpegReport:
    """Where ffmpeg is, and what does not work without it (`REQ-024`)."""

    path: Path | None
    source: str
    unavailable_features: tuple[str, ...] = field(default=())

    @property
    def available(self) -> bool:
        return self.path is not None

    def summary(self) -> str:
        """A sentence for the UI (`T-016`/`T-017` consume it).

        Deliberately names the features rather than saying "some features are unavailable" —
        and deliberately does **not** include the resolved path when ffmpeg is missing, since
        the only path in play then is a user-supplied override (`NFR-007`).
        """
        if self.available:
            return "ffmpeg found; all post-processing features are available."
        return "ffmpeg was not found. Unavailable: " + "; ".join(self.unavailable_features) + "."


def find_ffmpeg(
    override: Path | None = None,
    search_path: str | None = None,
) -> FfmpegReport:
    """Locate ffmpeg, honouring an explicit override first (`OPS-001`).

    Never runs a shell and never executes the binary — `ARCHITECTURE.md` §9 permits executing
    ffmpeg, but *detection* only needs to know it is there, and running an unknown executable
    to ask its version is a slower and larger-surface way to answer a smaller question. The
    version, if ever needed, belongs where ffmpeg is actually invoked.

    Returns rather than raises when absent: a missing ffmpeg disables features, it does not
    stop the application (`REQ-024`).
    """
    if override is not None:
        # An override that does not exist, or cannot be executed, is reported as missing rather
        # than silently ignored in favour of `PATH`. Silently falling back would mean the user's
        # explicit setting had no effect and nothing said so.
        #
        # `T035-R2`: presence alone is not enough. A regular file with mode 0644 was previously
        # reported available, and the summary claimed every post-processing feature worked when
        # nothing could run. `shutil.which` on a concrete path applies the platform's own
        # executable-discovery semantics — `F_OK | X_OK` on POSIX, `PATHEXT` on Windows — which
        # is exactly the check the `PATH` branch below already gets for free.
        resolved = shutil.which(str(override)) if override.is_file() else None
        if resolved is not None:
            return FfmpegReport(path=Path(resolved), source="explicit override (OPS-001)")
        return FfmpegReport(
            path=None,
            source="explicit override, not usable",
            unavailable_features=FFMPEG_DEPENDENT_FEATURES,
        )

    found = shutil.which(
        "ffmpeg", path=search_path if search_path is not None else os.environ.get("PATH")
    )
    if found:
        return FfmpegReport(path=Path(found), source="PATH")
    return FfmpegReport(
        path=None,
        source="not found on PATH",
        unavailable_features=FFMPEG_DEPENDENT_FEATURES,
    )


def describe_candidates(candidates: Sequence[YtdlpCandidate]) -> str:
    """A log-safe description of the resolution order.

    **No user path appears here** (`NFR-007`). The user-managed directory sits under the user's
    home, so logging it leaks a username into a file that may be attached to a bug report. The
    source label carries the useful information — *which* candidate was chosen — without it.
    """
    return ", ".join(candidate.source for candidate in candidates)
