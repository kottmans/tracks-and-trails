"""Error taxonomy and classification (`ARCHITECTURE.md` §7).

Every failure is classified, because the user-facing response differs per class: some are
worth retrying, some are permanent, and one — `DRM_PROTECTED` — must never be worked around
(`REQ-EXCL-001`, `SEC-001`).

Two properties here are load-bearing and easy to lose:

- **Classification never replaces the original message** (`NFR-006`, `REQ-005`). The extractor
  said something specific; paraphrasing it into "download failed" destroys the only
  information the user can act on. `FailureDetail` carries both, and the message is stored
  verbatim.
- **Auto-retry is opt-in per kind, and only `NETWORK` has it** (`REQ-018`). Silently retrying
  a permanent failure just hammers the site.

This module defines the taxonomy and how a classified failure is carried. It deliberately does
**not** map yt-dlp exceptions into it: `downloader/ytdlp_adapter.py` is the only place allowed
to import `yt_dlp` (`ARCHITECTURE.md` §6), so that mapping belongs to `T-012`. `classify()` is
the seam it plugs into.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final


class ErrorKind(StrEnum):
    """The `ARCHITECTURE.md` §7 taxonomy.

    `StrEnum` rather than `Enum`: these values are persisted in SQLite (`T-014`) and cross a
    process boundary (`ARC-002`), and a stable string is far easier to store, read in a log,
    and debug than an ordinal that shifts when a member is inserted.
    """

    UNSUPPORTED_URL = "unsupported_url"
    EXTRACTOR_ERROR = "extractor_error"
    AUTH_REQUIRED = "auth_required"
    GEO_RESTRICTED = "geo_restricted"
    DRM_PROTECTED = "drm_protected"
    NETWORK = "network"
    FFMPEG_MISSING = "ffmpeg_missing"
    FFMPEG_ERROR = "ffmpeg_error"
    DISK = "disk"
    WORKER_CRASH = "worker_crash"
    CANCELLED = "cancelled"


#: Kinds that may be retried at all, automatically or by the user.
#:
#: `DRM_PROTECTED` is excluded permanently and not as a policy tweak: retrying it is pointless,
#: and offering the button implies a workaround exists (`REQ-EXCL-001`). `CANCELLED` is
#: excluded because it is not a failure — the user asked for it, and "retry" there means
#: starting a new job, which is the caller's decision rather than this table's.
_NON_RETRYABLE: Final = frozenset({ErrorKind.DRM_PROTECTED, ErrorKind.CANCELLED})

#: The only kind that retries without asking (`REQ-018`, `ARCHITECTURE.md` §7).
#:
#: A set of one, spelled as a set on purpose: the day a second kind earns auto-retry, it is
#: added here rather than by rewriting a comparison somewhere else.
_AUTO_RETRYABLE: Final = frozenset({ErrorKind.NETWORK})


def is_retryable(kind: ErrorKind) -> bool:
    """Whether a job in this state may be retried at all, by the user or automatically."""
    return kind not in _NON_RETRYABLE


def is_auto_retryable(kind: ErrorKind) -> bool:
    """Whether the application may retry this without the user asking.

    Strictly narrower than `is_retryable`. Most failures are worth *offering* a retry for and
    wrong to retry unprompted — a private video does not become public because we asked twice.
    """
    return kind in _AUTO_RETRYABLE


@dataclass(frozen=True, slots=True)
class FailureDetail:
    """A classified failure, carrying the original message unchanged.

    Frozen and picklable: this crosses the process boundary from the worker back to the GUI
    (`ARC-002`), and a failure record that could be edited in flight would make the persisted
    history untrustworthy.
    """

    kind: ErrorKind

    #: The originating message, **verbatim** (`NFR-006`). Never paraphrased, never truncated,
    #: never replaced with a friendly summary. The UI may present it alongside its own text; it
    #: may not substitute for it.
    message: str

    #: Optional structured context — an ffmpeg exit code, a worker's exit status, the offending
    #: path. Kept separate from `message` so presentation can use it without parsing prose.
    context: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.message:
            raise ValueError(
                "a classified failure must carry the original message (NFR-006); "
                "an empty message discards the only actionable information there was"
            )

    @property
    def retryable(self) -> bool:
        return is_retryable(self.kind)

    @property
    def auto_retryable(self) -> bool:
        return is_auto_retryable(self.kind)


def classify(message: str, kind: ErrorKind | None = None, **context: str) -> FailureDetail:
    """Build a `FailureDetail`, defaulting to the least-committal classification.

    The seam `T-012` plugs the yt-dlp mapping into. When the caller cannot tell what went
    wrong, `EXTRACTOR_ERROR` is the honest default: `ARCHITECTURE.md` §7 pairs it with "show
    the extractor's message verbatim", which is exactly the right behavior when the only
    trustworthy information is the message itself.

    Guessing a more specific kind from message text is deliberately not done here. Substring
    matching on extractor prose is a maintenance trap — the strings change without notice, and
    a wrong guess is worse than no guess, because `DRM_PROTECTED` and `NETWORK` carry retry
    policy. `T-012` maps from yt-dlp's *exception types*, which are a real contract.
    """
    return FailureDetail(kind=kind or ErrorKind.EXTRACTOR_ERROR, message=message, context=context)
