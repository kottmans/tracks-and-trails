"""What each failure means, and what the user can do about it (`NFR-006`, `T-201`).

`NFR-006` asks for three things per error — **what failed, why, and what the user can do** — and
adds that extractor messages are *surfaced, never swallowed or replaced with a generic message*.
This module owns the first and third; the second is the extractor's own words, which are carried
alongside and never rewritten.

**Qt-free**, like `ui/format_text.py` beside it: this is a table of sentences, and a table of
sentences should be testable without a display.

## The class's text accompanies the message; it does not stand in for it

`core/errors.py` keeps the original verbatim precisely because paraphrasing destroys the only
information a user can act on. So `describe` returns the *frame* — a plain-words name for what
failed and an honest next step — and every caller renders it **with** `FailureDetail.message`
rather than instead of it.

## "Actionable" must not become "reassuring"

Three of the twelve have no honest action, and saying so is the deliverable rather than a gap:

- **`DRM_PROTECTED`** — there is nothing to do and `REQ-EXCL-001`/`REQ-EXCL-002` mean there must
  not be. It offers nothing and `core/errors.is_retryable` already refuses to retry it.
- **`GEO_RESTRICTED`** — the obvious suggestion is a proxy, and `SEC-003` ruled
  `--geo-verification-proxy` *in* while `REQ-EXCL-002` forbids bypassing a geo-restriction. **The
  line between them is a ruling nobody has taken**, so this text suggests no workaround at all —
  which is what the criterion requires and what leaves the ruling open. It is not phrased as
  though a proxy were unavailable, because that would take the ruling by implication in the other
  direction.
- **`CANCELLED`** is not a failure and is never presented as one.

A message that suggests an action which cannot work is worse than one that admits there is
none: it sends the user off to try things. `T-192` drew the same line for statuses with
`ACTIONABLE_STATUS_PROPERTY`, and this is that distinction for errors.

## Every kind is named here, and an unnamed one raises

`describe` looks the kind up in a table that must be total. A thirteenth `ErrorKind` added later
fails `test_every_error_kind_has_a_presentation` rather than quietly rendering as a bare
identifier — which is what the queue showed before this existed: `geo_restricted` on one line and
the extractor's sentence on the next.
"""

from dataclasses import dataclass
from typing import Final

from tracks_and_trails.core.errors import ErrorKind, is_retryable

__all__ = [
    "ErrorPresentation",
    "describe",
    "describe_failure",
    "headline_for",
    "next_step_for",
]


@dataclass(frozen=True, slots=True)
class ErrorPresentation:
    """One class of failure, in the words a user reads.

    `headline` is *what failed*, in plain language and without the taxonomy's identifier.
    `next_step` is *what to do*, or an empty string where there is honestly nothing — the empty
    case is meaningful and is asserted, because a table with a hopeful sentence in every row is
    the failure this task exists to prevent.
    """

    headline: str
    next_step: str

    #: What to say once the application has stopped retrying this by itself (`T201-R2`).
    #:
    #: **Empty for eleven of the twelve**, and that is the whole point of the field: only
    #: `NETWORK` is retried automatically, so only `NETWORK` has a state in which its own next
    #: step stops being true. A kind with nothing different to say after exhaustion keeps saying
    #: what it said before, which is what an empty value here means.
    exhausted_next_step: str = ""

    @property
    def has_next_step(self) -> bool:
        return bool(self.next_step)


#: What to say for each class. **Total over `ErrorKind`**, enforced by a test.
#:
#: The wording rules that are not obvious from reading it:
#:
#: - No sentence names a setting the application does not have. *"Try a proxy"* would name one
#:   `T-196` has not built, and a suggestion the user cannot act on is the reassuring-but-useless
#:   shape this module's docstring refuses.
#: - No sentence blames the user's connection for a failure that is not about the connection.
#: - `WORKER_CRASH` and `INTERRUPTED` are different events and say so: one was watched by the
#:   parent, the other was watched by nobody (`core/errors.py`).
_PRESENTATIONS: Final[dict[ErrorKind, ErrorPresentation]] = {
    ErrorKind.UNSUPPORTED_URL: ErrorPresentation(
        headline="This link is not one yt-dlp can download from",
        # Retry is refused for this below rather than suggested here: the same link will be
        # unsupported the second time, and `REQ-018`'s retry is for failures that can pass.
        next_step="Check the address, or try the page the media is embedded on.",
    ),
    ErrorKind.EXTRACTOR_ERROR: ErrorPresentation(
        headline="The site did not give up the media",
        # `C-002`: site support *is* yt-dlp's site support, so the update action `REQ-025` builds
        # is the honest first move rather than a platitude about trying later.
        next_step="The site may have changed. Updating yt-dlp in Settings often fixes this.",
    ),
    ErrorKind.AUTH_REQUIRED: ErrorPresentation(
        headline="This needs an account that is signed in",
        # Names the setting that exists, and stops short of promising it will work: cookies reach
        # what the account can already reach, which is what the cookies section itself says.
        next_step="Set a cookies file in Settings for an account that can already see it.",
    ),
    ErrorKind.GEO_RESTRICTED: ErrorPresentation(
        headline="The site refused this from your location",
        # **Deliberately no next step.** See the module docstring: the line between a user's own
        # proxy and circumventing a restriction is a ruling nobody has taken, and `REQ-EXCL-002`
        # forbids the second. Suggesting nothing leaves the ruling open in both directions.
        next_step="",
    ),
    ErrorKind.DRM_PROTECTED: ErrorPresentation(
        headline="This is DRM-protected, and Tracks & Trails does not remove DRM",
        # Nothing, permanently, and `REQ-EXCL-001` is why. Retry is refused in `core/errors.py`
        # rather than here, so the two cannot disagree.
        next_step="",
    ),
    ErrorKind.NETWORK: ErrorPresentation(
        headline="The connection to the site failed",
        # The only auto-retryable kind, so the sentence says the application is already trying —
        # otherwise a user reads "check your connection" while a retry they were not told about
        # is in flight. **Bounded, and it says so** (`T201-R2`): the automatic retries run out,
        # and a sentence that promises another one at the moment none remains is the reassuring
        # text this module exists to refuse. `exhausted_next_step` is what the last failure gets.
        next_step="This retries by itself a few times. Check your connection if it keeps failing.",
        # **What the *final* failure says**, once `AUTOMATIC_RETRY_LIMIT` attempts are spent. Not
        # a variant of the sentence above: at that point nothing is in flight, and the honest
        # instruction is the button the row is already offering.
        exhausted_next_step="The automatic retries are used up. Check your connection and press "
        "Retry.",
    ),
    ErrorKind.FFMPEG_MISSING: ErrorPresentation(
        headline="This download needed ffmpeg, which was not found",
        next_step="Install ffmpeg, or point Settings at it, then retry.",
    ),
    ErrorKind.FFMPEG_ERROR: ErrorPresentation(
        headline="ffmpeg was found but could not finish the job",
        next_step="Retry, or choose a format that needs no conversion.",
    ),
    ErrorKind.DISK: ErrorPresentation(
        headline="The file could not be written",
        next_step="Check there is free space and that the download folder can be written to.",
    ),
    ErrorKind.WORKER_CRASH: ErrorPresentation(
        headline="The download process stopped unexpectedly",
        next_step="Retry. If it happens repeatedly, the log for this job has the detail.",
    ),
    ErrorKind.INTERRUPTED: ErrorPresentation(
        # Distinct from a crash, and the difference is what was observed: nobody watched this
        # one. Saying "crashed" would claim knowledge the application does not have.
        headline="Tracks & Trails closed while this was downloading",
        next_step="Retry to start it again.",
    ),
    ErrorKind.CANCELLED: ErrorPresentation(
        # **Not a failure**, and never drawn as one (`ARCHITECTURE.md` §7). No next step, because
        # nothing went wrong: starting again is a new job the user decides on, not a repair.
        headline="You cancelled this download",
        next_step="",
    ),
}


def describe(kind: ErrorKind) -> ErrorPresentation:
    """The presentation for `kind`, or `KeyError` if one was never written.

    **Raising is the point.** A `.get()` with a generic fallback would let a new `ErrorKind`
    reach a user as *"Download failed"*, which is the exact sentence `NFR-006` forbids — and it
    would do so silently, which is how the taxonomy's identifiers ended up on screen in the first
    place.
    """
    return _PRESENTATIONS[kind]


def headline_for(kind: ErrorKind) -> str:
    """What failed, in plain words. Rendered *with* the extractor's message, never instead."""
    return describe(kind).headline


def next_step_for(kind: ErrorKind, *, exhausted: bool = False) -> str:
    """What to do, or `""` where there is honestly nothing.

    **Consistent with `core/errors.is_retryable` by construction**: a kind that may not be
    retried is never given a step that says to retry. The two are checked against each other by
    `test_no_unretryable_kind_is_told_to_retry` rather than kept in line by memory.

    **`exhausted` is whether the automatic retries are spent** (`T201-R2`), which only the caller
    can know: the bound lives on `DownloadManager` and this module may not import Qt. It was
    missing, and the cost was exact — `NETWORK` said *"This one retries by itself"* on the fourth
    and final failure, at the one moment no automatic retry remained. That is this task's named
    risk in its own words: **reassuring text that is no longer true.**

    A kind with no separate exhausted wording keeps its ordinary one, which is eleven of the
    twelve — nothing else is retried automatically, so nothing else has a state to leave.
    """
    presentation = describe(kind)
    step = presentation.next_step
    if exhausted and presentation.exhausted_next_step:
        step = presentation.exhausted_next_step
    if not is_retryable(kind) and "retry" in step.lower():
        # Unreachable while the table above holds, and cheap insurance if it is edited: the
        # alternative is a screen telling a user to press a button that is deliberately absent.
        return ""
    return step


def describe_failure(kind: ErrorKind, message: str, *, exhausted: bool = False) -> str:
    """The whole thing a surface shows: what failed, what to do, then the extractor's own words.

    **The message goes last and unchanged.** `NFR-006` requires it surfaced rather than swallowed
    or replaced, and `core/errors.py` stores it verbatim for the same reason — so this composes
    around it and never edits it. A class with nothing to suggest contributes two lines instead of
    three rather than a hopeful sentence (`GEO_RESTRICTED`, `DRM_PROTECTED`, `CANCELLED`).

    An empty `message` is normal: a worker that crashed before it could say anything still has a
    class, and the headline is what the user reads then.
    """
    lines = [headline_for(kind)]
    step = next_step_for(kind, exhausted=exhausted)
    if step:
        lines.append(step)
    if message.strip():
        lines.append(message)
    return "\n".join(lines)
