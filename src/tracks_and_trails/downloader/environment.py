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
from pathlib import Path
from typing import Final

from platformdirs import user_data_dir

#: Matches `ARCHITECTURE.md` §5's paths and `ui/main_window.py`'s slug.
APP_SLUG: Final = "tracksandtrails"

#: Features that need ffmpeg, named in the terms a user would recognise (`REQ-024`, `REQ-010`).
#:
#: Spelled out rather than "some features are unavailable": a user who is told *what* stops
#: working can decide whether they care, and one who is told nothing files a bug instead.
FFMPEG_DEPENDENT_FEATURES: Final = (
    "merging separate video and audio streams",
    "extracting or converting audio",
    "remuxing and recoding",
    "embedding thumbnails, metadata, chapters and subtitles",
)


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
    `worker.py`. `exists` reports only what is on disk.
    """

    #: `None` means "already importable from the environment" — the bundled baseline, or the
    #: development virtualenv. `worker.py` imports without touching `sys.path` in that case.
    path: Path | None
    source: str
    exists: bool


def ytdlp_candidates(user_directory: Path | None = None) -> tuple[YtdlpCandidate, ...]:
    """Candidate locations in the order `worker.py` must try them (`ARCHITECTURE.md` §6).

    The user-managed copy first, then the bundled baseline. A user copy is listed **even when
    the directory is empty or holds no `yt_dlp` package**: deciding it is unusable requires
    importing it, and `worker.py` owns that. Filtering here on a `yt_dlp/` directory check
    would be this module quietly forming the verdict it is not allowed to form — and it would
    be wrong for a wheel layout this code has not anticipated.
    """
    directory = user_ytdlp_directory() if user_directory is None else user_directory
    return (
        YtdlpCandidate(
            path=directory,
            source="user-managed copy (OPS-002)",
            exists=directory.is_dir(),
        ),
        YtdlpCandidate(
            path=None,
            source="bundled baseline",
            exists=True,
        ),
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
        # An override that does not exist is reported as missing rather than silently ignored
        # in favour of `PATH`. Silently falling back would mean the user's explicit setting had
        # no effect and nothing said so.
        if override.is_file():
            return FfmpegReport(path=override, source="explicit override (OPS-001)")
        return FfmpegReport(
            path=None,
            source="explicit override, not found",
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
    return ", ".join(
        f"{candidate.source} ({'present' if candidate.exists else 'absent'})"
        for candidate in candidates
    )
