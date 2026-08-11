"""Domain models: Job, DownloadRequest, MediaInfo, FormatInfo, Preset.

The pure-domain foundation of the vertical slice (`T-010`). No Qt, no yt-dlp, no I/O beyond
the standard library — `core/` is the layer that stays testable headless and is reused by both
the GUI process and the spawned worker (`ARCHITECTURE.md` §4).

Two properties are load-bearing and easy to lose:

- **Everything here crosses a process boundary** (`ARC-002`). Every type must be picklable:
  plain dataclasses and enums, no lambdas, no open handles, no `functools.partial`. The tests
  assert this per type, so the day someone adds an unpicklable field it fails loudly rather
  than at the first real download.
- **`DownloadRequest` is frozen at job-creation time** (`ARCHITECTURE.md` §8). A running job
  never observes a mid-flight settings change, which is what makes the worker's behavior
  reproducible from the request alone — and what makes a retry repeat the *original* request
  rather than today's defaults (`REQ-018`).

Every model here is frozen. Immutability is not stylistic: these objects are read on the GUI
thread, sent to a worker process, and persisted, and a shared mutable job is how a queue
silently disagrees with its own database.

`HistoryEntry` **no longer exists**, and this paragraph is kept as the reason it never lived
here. It was named in `ARCHITECTURE.md` §5 and defined with the schema that stored it (`T-014`),
because a durable record is not live domain state. `REQ-020` was withdrawn on 2026-08-06 and
migration `0009` dropped the table; `T-175` removed the type. The rule the paragraph states —
durable records belong with their schema, not in this module — is why it is worth keeping
(`T-176`).
"""

import os
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any, ClassVar, Final, Self
from urllib.parse import urlsplit

from tracks_and_trails.core.errors import ErrorKind
from tracks_and_trails.core.job_state import JobStatus, apply

# --- field validation -----------------------------------------------------------------------
#
# `T011-R8` found that `MediaInfo(formats=[{...}])` stored a mutable list of raw yt-dlp format
# dicts — so raw upstream data crossed the process boundary inside a `Probed` message that
# validated, and could still be mutated afterwards. `downloader/protocol.py` correctly rejects a
# non-`MediaInfo`; nothing checked what a `MediaInfo` contained.
#
# The audit that followed found the hole was not one field. **Every** field of every model here
# accepted an arbitrary dict or list: the only checks were emptiness and negativity, and a
# non-empty dict passes both. These helpers close the class rather than the instance, which is
# the lesson `T011-R2` had to be reopened to teach.
#
# Deliberately duplicated in miniature from `downloader/protocol.py` rather than shared:
# `T-041`'s scope puts that module out of bounds, and exporting private validators across a
# layer boundary to save ten lines is a worse trade. `normalise_context()` *is* shared, because
# there the risk was two hand-written copies of one subtle normalisation drifting apart.


def _fail(owner: str, name: str, value: object, expected: str) -> None:
    raise TypeError(f"{owner}.{name} must be {expected}, not {type(value).__name__}")


def _require_text(owner: str, name: str, value: object, reason: str = "") -> None:
    """A non-empty string.

    `TypeError` for the wrong type, `ValueError` for a validly typed empty string. `T041-R4`:
    the bespoke truthiness checks these replace raised `ValueError` for both, so a caller could
    not tell a type error from an empty one. `reason` keeps the explanatory messages those
    checks carried — the *why* is often the useful half.
    """
    if not isinstance(value, str):
        _fail(owner, name, value, "a string")
    if not value:
        raise ValueError(f"{owner}.{name} cannot be empty{'; ' + reason if reason else ''}")


def _is_ytdlp_quality(value: str) -> bool:
    """Whether `value` is something yt-dlp's `preferredquality` accepts.

    Validated here rather than discovered at post-processing time: that happens *after* the
    file has been downloaded, so a typo would cost the user the whole transfer before failing.
    """
    return value.isdigit()


#: The browsers yt-dlp can read cookies from, lower-cased (`REQ-026`).
#:
#: **A closed list, because the point is to refuse a path.** Taken from yt-dlp's own
#: `--cookies-from-browser` support; a name it does not know is refused here rather than reaching
#: the library, which is the same *bound at the value* rule `REQ-013`'s limits follow.
BROWSER_NAMES: Final = (
    "brave",
    "chrome",
    "chromium",
    "edge",
    "firefox",
    "opera",
    "safari",
    "vivaldi",
    "whale",
)


#: The keyrings yt-dlp can read a browser's cookie encryption key from.
KEYRING_NAMES: Final = ("basictext", "gnomekeyring", "kwallet", "kwallet5", "kwallet6")

#: yt-dlp's own `--cookies-from-browser` grammar: `BROWSER[+KEYRING][:PROFILE][::CONTAINER]`.
#:
#: Transcribed rather than imported, because `core/**` may not import `yt_dlp`
#: (`ARCHITECTURE.md` §6). `tests/unit/test_models.py` binds `BROWSER_NAMES` and `KEYRING_NAMES`
#: to yt-dlp's own `SUPPORTED_BROWSERS` and `SUPPORTED_KEYRINGS`, in the layer that may import
#: both — the same device `THEME_NAMES` uses, and the only thing that stops two lists drifting.
#: `%NAME%`, the Windows environment-variable form `expandvars` expands.
_WINDOWS_VARIABLE: Final = re.compile(r"%[^%]+%")

_BROWSER_SPEC: Final = re.compile(
    r"^(?P<name>[^+:\s]+)"
    r"(?:\s*\+\s*(?P<keyring>[^:\s]+))?"
    r"(?:\s*:\s*(?!:)(?P<profile>[^:]+?))?"
    r"(?:\s*::\s*(?P<container>.+))?$"
)


def parse_browser_specification(value: str) -> tuple[str, str | None, str | None, str | None]:
    """Split `BROWSER[+KEYRING][:PROFILE][::CONTAINER]` into what yt-dlp wants (`T-197`).

    Returns `(browser, profile, keyring, container)` — **yt-dlp's own argument order**, so the
    adapter can hand the tuple over without reordering it at the boundary where a mistake is
    invisible.

    **Raises `ValueError` for anything this application will not carry**, which is the whole
    reason it exists rather than the string being passed through: `T197-R2` found that
    `firefox:/home/alice/.mozilla/cookies.sqlite` was accepted, so a **path** reached the model
    and the job JSON through the profile portion — the exact leak the browser check was added to
    close, one component to the right. yt-dlp itself accepts a profile *path*; this application
    does not, because `DAT-003` forbids a cookie path in the model and a narrower capability is
    the price of that guarantee being structural.
    """
    match = _BROWSER_SPEC.match(value.strip())
    if match is None:
        raise ValueError(f"{value!r} is not BROWSER[+KEYRING][:PROFILE][::CONTAINER]")
    browser = (match.group("name") or "").strip().lower()
    if browser not in BROWSER_NAMES:
        raise ValueError(f"{browser!r} is not one of {', '.join(BROWSER_NAMES)}")
    keyring = match.group("keyring")
    if keyring is not None and keyring.strip().lower() not in KEYRING_NAMES:
        raise ValueError(f"{keyring!r} is not one of {', '.join(KEYRING_NAMES)}")
    profile = match.group("profile")
    if profile is not None:
        profile = profile.strip()
        if looks_like_a_path(profile):
            raise ValueError(
                f"the profile {profile!r} is a path. A cookie path is a settings value and never "
                "a field on this model (DAT-003); name the profile instead"
            )
    container = match.group("container")
    if container is not None:
        container = container.strip()
        # **The fourth and last component, checked like the second and third** (`T197-R2`,
        # reopened). The profile was path-checked and the container was not, so
        # `firefox::/home/alice/session.txt` rode the unchecked slot into the job JSON — the
        # third time a path slipped one component right of the check. The grammar has exactly
        # four components: browser and keyring are closed lists, and profile and container now
        # share one predicate. There is no fifth slot for this finding to move to.
        if looks_like_a_path(container):
            raise ValueError(
                f"the container {container!r} is a path. A cookie path is a settings value and "
                "never a field on this model (DAT-003); name the container instead"
            )
    return (
        browser,
        profile or None,
        keyring.strip().upper() if keyring else None,
        container or None,
    )


def looks_like_a_path(value: str) -> bool:
    """Whether `value` names a location rather than a profile (`T197-R2`).

    **Two questions, and the second is asked the way yt-dlp asks it.** A separator or a drive
    letter is a path outright. And yt-dlp runs a profile through `expand_path`, which is
    `expandvars(expanduser(...))` — so `firefox:$HOME` passes any check on the *written* characters
    and becomes `/home/sean` inside the library. The review reproduced exactly that.

    **So expansion is performed here, with the standard library yt-dlp itself uses, and a profile
    that changes under it is refused.** That is not a denylist of `$`, `%` and `~` — it is the same
    transformation, asked whether it does anything. A denylist is the enumeration failure
    `DAT-003` records twice; this cannot miss a spelling because it is not matching spellings.
    """
    if "/" in value or "\\" in value or (len(value) > 1 and value[1] == ":"):
        return True
    # **The expansion *syntax*, refused structurally**, because performing the expansion is not
    # enough on its own: `~x` expands only where a user `x` exists, and `%USERPROFILE%` only on
    # Windows — so the check below answers differently on different machines, which is the
    # platform-dependent class that has already cost this project three findings. These three
    # forms are the whole of what `expanduser` and `expandvars` implement; the list is closed
    # because it describes a syntax, not a set of secrets.
    if value.startswith("~") or "$" in value or _WINDOWS_VARIABLE.search(value):
        return True
    # `os.path`, not `Path`, and the linter's suggestion is wrong here: `Path.expanduser()`
    # normalises separators and drops a trailing slash, so it would answer *changed* for strings
    # that expand to themselves. This has to be the exact pair yt-dlp applies.
    return os.path.expandvars(os.path.expanduser(value)) != value  # noqa: PTH111


def _require_browser_name(owner: str, name: str, value: object) -> None:
    """Refuse anything that is not a browser specification this application can carry.

    `T-197`, `DAT-003`. The check is the full grammar rather than the first component, because
    `T197-R2` proved the first component alone lets a path through the second.
    """
    if value is None:
        return
    if not isinstance(value, str):  # pragma: no cover - `_require_optional_text` refuses first
        return
    try:
        parse_browser_specification(value)
    except ValueError as refusal:
        raise ValueError(f"{owner}.{name} is {value!r}: {refusal}") from refusal


def _require_optional_text(owner: str, name: str, value: object) -> None:
    if value is not None and not isinstance(value, str):
        _fail(owner, name, value, "a string or None")


def _require_count(owner: str, name: str, value: object) -> None:
    """A non-negative `int`. **Not** optional.

    `T041-R1`: `bytes_done` and `attempts` were routed through the *optional* validator, so both
    accepted and stored `None` despite `int` annotations and `0` defaults. That moves an invalid
    value toward persistence and makes `Job.progress` raise when a total is present.
    """
    if value is None:
        raise ValueError(f"{owner}.{name} is required and cannot be None")
    _require_optional_count(owner, name, value)


def _require_optional_count(owner: str, name: str, value: object) -> None:
    """A non-negative `int` or `None`. `bool` is rejected: it is an `int` subclass."""
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(owner, name, value, "an int or None")
    if value < 0:  # type: ignore[operator]
        raise ValueError(f"{owner}.{name} cannot be negative")


def _require_optional_duration(owner: str, name: str, value: object) -> None:
    """A non-negative real number or `None`. Durations are legitimately fractional."""
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int | float):
        _fail(owner, name, value, "a number or None")
    if value < 0:  # type: ignore[operator]
        raise ValueError(f"{owner}.{name} cannot be negative")


def _require_flag(owner: str, name: str, value: object) -> None:
    """Strictly `bool` — not merely truthy. A non-empty dict is truthy."""
    if not isinstance(value, bool):
        _fail(owner, name, value, "a bool")


def _require_optional_flag(owner: str, name: str, value: object) -> None:
    """`True`, `False` or **`None` meaning nobody said** (`T-108`).

    Separate from `_require_flag` rather than a parameter on it, because the two encode different
    promises: a flag is a fact the projection always has, and this is one it may not. `0` and `1`
    are refused for the same reason `_require_flag` refuses them — `has_video=0` reading as *"no
    video"* by truthiness is the bug this type exists to make unrepresentable.
    """
    if value is not None and not isinstance(value, bool):
        _fail(owner, name, value, "a bool or None")


def _require_enum[E: Enum](owner: str, name: str, value: object, enum: type[E]) -> None:
    """An actual enum member.

    `StrEnum` members compare equal to their string values, so a bare string mostly works
    until something does an identity check — the failure mode `T011-R2` recorded.
    """
    if not isinstance(value, enum):
        _fail(owner, name, value, f"a {enum.__name__} member")


def _require_optional_enum[E: Enum](owner: str, name: str, value: object, enum: type[E]) -> None:
    if value is not None and not isinstance(value, enum):
        _fail(owner, name, value, f"a {enum.__name__} member or None")


def _require_model[T](owner: str, name: str, value: object, model: type[T]) -> None:
    """Exactly `model` — **not** a subclass (`T041-R3`).

    A frozen subclass can declare extra fields that this module never validates, including a
    mutable dict, and carry them through the process boundary inside an otherwise valid graph.
    That is the same reason `T-011` moved `is_message()` from `isinstance` to an exact type
    match: "declared" is the invariant, and a subclass is not declared.
    """
    if type(value) is not model:
        _fail(owner, name, value, f"exactly a {model.__name__}")


def _require_credential_free_proxy(value: str | None) -> None:
    """Reject a proxy that is not `scheme://host[:port]`, or that carries userinfo (`T014-R1`).

    **Credentials are made unrepresentable rather than removed.** This field accepted any
    non-empty string, so persistence had no grammar to parse and every attempt to strip secrets
    was a scan of unbounded text. Three separate credential forms reached the database that way —
    scheme-less, then Unicode and single-label hosts, then scheme-relative — and one attempt to
    scrub them corrupted legitimate output paths instead.

    A job therefore cannot hold a proxy password at all. `REQ-026` covers authenticated *content*
    via cookies; it does not require an authenticated proxy, and if one is ever needed it belongs
    in the settings layer with its own handling rather than inside a persisted, IPC-crossing job.
    """
    if value is None:
        return
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(
            f"DownloadRequest.proxy must be scheme://host[:port], not {value!r}. A value without "
            "an explicit scheme — including the scheme-relative //host form — has no unambiguous "
            "parse, which is how three separate credential forms reached the database."
        )
    if "@" in parsed.netloc:
        raise ValueError(
            "DownloadRequest.proxy must not carry credentials. A job is persisted and crosses a "
            "process boundary, so a password here would be written to the database (REQ-026). "
            "Use a proxy without userinfo."
        )
    if parsed.path.strip("/") or parsed.query or parsed.fragment:
        raise ValueError(
            f"DownloadRequest.proxy must be scheme://host[:port] with no path, query or "
            f"fragment, not {value!r}."
        )


def _require_optional_datetime(owner: str, name: str, value: object) -> None:
    if value is not None and not isinstance(value, datetime):
        _fail(owner, name, value, "a datetime or None")


def _as_tuple_of[T](owner: str, name: str, value: object, element: type[T]) -> tuple[T, ...]:
    """Return `value` as a tuple, rejecting a non-sequence or a wrong element type.

    Normalising a list to a tuple is deliberate: the element types are what matter, and a
    caller passing a list is not making a mistake. Storing it as a tuple is what stops the
    caller's list from mutating a model that has already been sent (`T010-R2`) — a frozen
    dataclass holding a list is only shallowly frozen.

    A `str` is a `Sequence` and is rejected explicitly, or `"abc"` would silently become
    `("a", "b", "c")`.
    """
    if isinstance(value, str) or not isinstance(value, Sequence):
        _fail(owner, name, value, f"a sequence of {element.__name__}")
    items: tuple[Any, ...] = tuple(value)  # type: ignore[arg-type]
    for index, item in enumerate(items):
        # Exact type, not isinstance (`T041-R3`): a `FormatInfo` subclass carrying an extra
        # mutable field would otherwise ride along inside a validated `MediaInfo`.
        if type(item) is not element:
            raise TypeError(
                f"{owner}.{name}[{index}] must be a {element.__name__}, "
                f"not {type(item).__name__}"
                + (
                    " — a raw yt-dlp dict must never reach a domain model (ARC-002)"
                    if isinstance(item, dict)
                    else ""
                )
            )
    return items


class MediaKind(StrEnum):
    """What a preset or request is asking for.

    Video and audio are equal first-class citizens — the project's premise, not a detail
    (`README`, `REQ-002`). Neither is the default the other opts out of.
    """

    VIDEO = "video"
    AUDIO = "audio"


class AudioCodec(StrEnum):
    """The audio codec a request asks for (`REQ-010`'s "chosen codec").

    `REQ-006` requires **audio only (MP3)** and **audio only (best/original)** as two distinct
    presets. Without this the two were indistinguishable: both installed yt-dlp's audio
    extractor with its default `best`, which *keeps* the source codec — so the MP3 preset
    delivered whatever the site served and silently never converted anything (`T012-R5`).

    Values are yt-dlp's own `preferredcodec` vocabulary so translation is a lookup rather than
    a mapping table that can drift. `ORIGINAL` is spelled for the user's benefit and carries
    yt-dlp's `best`, which means "no conversion", not "the highest-quality codec".
    """

    ORIGINAL = "best"
    MP3 = "mp3"
    AAC = "aac"
    M4A = "m4a"
    OPUS = "opus"
    VORBIS = "vorbis"
    FLAC = "flac"
    ALAC = "alac"
    WAV = "wav"


#: Codecs whose delivery requires a conversion step, and therefore ffmpeg (`REQ-024`).
#:
#: `ORIGINAL` is absent deliberately: it copies the source stream, so it is the one audio
#: request that does not by itself demand ffmpeg.
CONVERTING_AUDIO_CODECS: Final = frozenset(AudioCodec) - {AudioCodec.ORIGINAL}

#: The containers `REQ-010`'s remux and recode options may target (`T-109`).
#:
#: **A copy of yt-dlp's `SUPPORTED_EXTS`, and the copy is deliberate.** `core/` may not import
#: `yt_dlp` (`ARCHITECTURE.md` §6), so the list cannot be read from the library here — and it has
#: to be checkable *here*, because `__post_init__` is where a container that yt-dlp will refuse
#: gets caught before the download is paid for. That is `audio_quality`'s argument one field over.
#:
#: The drift this buys is answered rather than accepted: `tests/unit/test_ytdlp_adapter.py`
#: asserts this tuple **equals** `FFmpegVideoRemuxer.SUPPORTED_EXTS` and
#: `FFmpegVideoConvertor.SUPPORTED_EXTS`, so a version that adds a container fails the suite
#: instead of quietly refusing one a user could have had. `MERGE_TOKENS` in `core/presets.py` is
#: the same shape for the same reason.
#:
#: Video containers first, then audio-only ones, in yt-dlp's own order — a remux target of `mp3`
#: is legal and occasionally what somebody wants, so the list is not filtered by `media_kind`.
CONTAINER_FORMATS: Final[tuple[str, ...]] = (
    "avi",
    "flv",
    "gif",
    "mkv",
    "mov",
    "mp4",
    "webm",
    "aac",
    "aiff",
    "alac",
    "flac",
    "m4a",
    "mka",
    "mp3",
    "ogg",
    "opus",
    "vorbis",
    "wav",
)


def _require_container(owner: str, name: str, value: object) -> None:
    """`value` is `None` or a container yt-dlp's remuxer and recoder both accept (`REQ-010`).

    Rejected here rather than left to yt-dlp for `audio_quality`'s reason: the postprocessor
    raises after the download has finished, so a typo costs the whole transfer. The message names
    the list because a user typing a container wants to know which ones exist.
    """
    _require_optional_text(owner, name, value)
    if value is not None and value not in CONTAINER_FORMATS:
        raise ValueError(
            f"{owner}.{name} must be one of {list(CONTAINER_FORMATS)}, not {value!r}; yt-dlp "
            "refuses anything else at post-processing time, which is after the download has "
            "already been paid for"
        )


def _require_one_container_change(owner: str, remux: str | None, recode: str | None) -> None:
    """A request may remux **or** recode, not both (`REQ-010`, `T-109`).

    yt-dlp would run both postprocessors in turn, so the pair is expressible upstream — and it
    expresses two contradictory intentions. A remux rewrites the container and keeps the streams;
    a recode re-encodes them. Asking for both means the remux's output is immediately re-encoded,
    which is the recode alone with a wasted pass, and no UI could present it as anything a user
    meant.

    Refused at construction rather than resolved by precedence, because a silent winner is how a
    control comes to appear to do nothing — `T-075`'s defect, and the reason `with_audio_quality`
    raises rather than ignoring a bitrate it cannot honour.
    """
    if remux is not None and recode is not None:
        raise ValueError(
            f"{owner} asks to remux to {remux!r} and recode to {recode!r}; those are two "
            "different intentions for one container and yt-dlp would do both in turn. Choose "
            "remux to rewrap the streams, or recode to re-encode them."
        )


@dataclass(frozen=True, slots=True)
class FormatInfo:
    """One selectable format from a probe — a projection of yt-dlp's format dict.

    Declared fields only (`ARCHITECTURE.md` §5). Carrying the raw dict through the application
    would spread yt-dlp's schema into every layer and defeat `NFR-008`'s containment of
    upstream churn.
    """

    format_id: str
    extension: str

    #: Every field below is optional because yt-dlp genuinely omits them. A live stream has no
    #: filesize, an audio-only format has no height, and a storyboard has no codec. Modelling
    #: them as required would mean inventing values, which the UI would then display.
    height: int | None = None
    width: int | None = None
    filesize: int | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    note: str | None = None

    #: Frames per second, and the total bitrate in kbps (`REQ-003`, added by `T-107`).
    #:
    #: **`REQ-003` has named both since it was written and neither had anywhere to live**, so the
    #: table that requirement asks for could not have been populated from a declared field. This is
    #: the projection catching up with the requirement rather than a new capability.
    #:
    #: **Fractional on purpose.** yt-dlp reports `fps` as a float — 29.97 and 59.94 are ordinary —
    #: and `tbr` likewise. Rounding here would put the rounding in the projection, where nothing
    #: can undo it, instead of in the one place that renders it.
    #:
    #: **`bitrate_kbps` is yt-dlp's `tbr`, the *total* rate**, not `vbr` or `abr`. `REQ-003` names
    #: one bitrate column, and total is the one that means something for both a progressive format
    #: and an audio-only one. The split rates stay unprojected until something asks for them.
    fps: float | None = None
    bitrate_kbps: float | None = None

    #: Whether `filesize` is yt-dlp's estimate rather than a size it was told (`T107-R7`).
    #:
    #: **`REQ-003` names the column "filesize/estimate" and the two were indistinguishable.**
    #: `project_format` accepts `filesize_approx` as a fallback for `filesize`, which is right —
    #: a user wants a number — but it collapsed the provenance, so an estimate rendered exactly
    #: like a measured size. The reviewer projected an exact and an approximate 4 MiB entry and
    #: got equal `FormatInfo`s and the same `4.0 MB` text.
    #:
    #: A flag rather than a second size field: there is only ever one number, and two nullable
    #: size fields would make every reader ask which to prefer.
    filesize_is_estimate: bool = False

    #: Whether the format carries a video / an audio stream at all — **three states, not two**
    #: (`REQ-008`, `T-108`).
    #:
    #: `True` it has one, `False` it explicitly has none, **`None` nobody said**. yt-dlp writes
    #: `vcodec: 'none'` to mean *there is no video here*, and omits the key when it does not know;
    #: `_as_optional_codec` maps both to `None`, so `video_codec is None` cannot tell them apart.
    #:
    #: **`T107-R1` is what that costs.** The table rendered *audio only* for a format whose video
    #: codec was merely unknown, because `is_audio_only` reads the collapsed field. That was fixed
    #: by declining to assert anything; `REQ-008` cannot decline, because *"a separate video and
    #: audio stream to be merged"* requires knowing which is which before either can be routed to a
    #: slot. `format_table.describe_resolution` names this widening as the thing it was waiting for.
    #:
    #: Two flags rather than one `kind` enum: the two streams are independently known or unknown —
    #: media.ccc.de reports `vcodec: 'none'` beside a named `acodec`, and `vcodec: 'h264'` beside no
    #: `acodec` at all, in the same item — and an enum would have to invent a name for each of the
    #: nine combinations to say what two tri-states say directly.
    has_video: bool | None = None
    has_audio: bool | None = None

    def __post_init__(self) -> None:
        _require_text("FormatInfo", "format_id", self.format_id, "it is how a format is selected")
        _require_text("FormatInfo", "extension", self.extension)
        for name in ("height", "width", "filesize"):
            _require_optional_count("FormatInfo", name, getattr(self, name))
        for name in ("video_codec", "audio_codec", "note"):
            _require_optional_text("FormatInfo", name, getattr(self, name))
        # `_require_optional_duration` is the non-negative-real validator, named for its first
        # caller rather than for what it checks. Reused rather than copied: fps and a bitrate have
        # exactly its shape — optional, fractional, never negative — and a second identical
        # validator is a second thing to keep in step.
        for name in ("fps", "bitrate_kbps"):
            _require_optional_duration("FormatInfo", name, getattr(self, name))
        _require_flag("FormatInfo", "filesize_is_estimate", self.filesize_is_estimate)
        if self.filesize_is_estimate and self.filesize is None:
            # An estimate of nothing is not a state: the flag qualifies a number, and a reader
            # that trusted it without one would render "~Unknown".
            raise ValueError("FormatInfo.filesize_is_estimate is set with no filesize to qualify")
        for name in ("has_video", "has_audio"):
            _require_optional_flag("FormatInfo", name, getattr(self, name))
        for stream, present, codec in (
            ("video", self.has_video, self.video_codec),
            ("audio", self.has_audio, self.audio_codec),
        ):
            if present is False and codec is not None:
                # A named codec for a stream declared absent is not a value this projection can
                # hold: one of the two came from somewhere else. Refusing here rather than letting
                # a selection routine decide which to believe (`T-010`'s rule, one field over).
                raise ValueError(
                    f"FormatInfo says it has no {stream} and names a {stream} codec "
                    f"{codec!r}; one of the two is wrong"
                )

    @property
    def is_audio_only(self) -> bool:
        """yt-dlp said this format has **no video**, and did not deny it audio (`T-108`).

        *Was* `video_codec is None and audio_codec is not None`, which read a missing `vcodec` as an
        absent video stream — `T107-R1`, where a format with an unknown video codec was reported as
        having no video at all. `has_video` keeps yt-dlp's `'none'` apart from its silence, so the
        property can mean what its name says.

        **The `'none'` is the whole signal; the other side may be silent.** A real HLS
        `EXT-X-MEDIA:TYPE=AUDIO` rendition arrives as `vcodec: 'none'` with **no `acodec` at all**,
        because the codec list lives on the variant rather than on the group — so requiring a named
        audio codec would make the commonest real audio stream not audio-only. Silence on its own
        still says nothing: `has_video` must be an explicit `False`.

        A format denied *both* streams — a storyboard — is neither half, which is why `has_audio is
        not False` is part of it rather than an afterthought.

        **`format_selection.kind_of` is defined in terms of this property**, so the routing and the
        model cannot come to differ about what "audio only" means.
        """
        return self.has_video is False and self.has_audio is not False

    @property
    def is_video_only(self) -> bool:
        """The mirror image: **no audio**, and video not denied — the other half of a merge pair.

        Deliberately symmetrical with `is_audio_only`, down to the `is not False`: media.ccc.de
        publishes `vcodec: 'h264'` with no `acodec` for recordings that certainly have sound, and
        that is `has_audio is None` rather than `False`, so it is **not** video-only.
        """
        return self.has_audio is False and self.has_video is not False


@dataclass(frozen=True, slots=True)
class PlaylistEntry:
    """One item of a playlist, as a flat extraction reports it (`T-137`, `REQ-002`).

    **Deliberately not a `MediaInfo`.** An entry carries what `extract_flat` gives cheaply — an
    address and a name — and nothing that would require extracting the item itself. Projecting a
    full `MediaInfo` per entry would make probing a playlist cost one extraction per item, which is
    the cost `project_media` refused to pay when it declined to project entries at all.

    So the fields here are the ones a **queue row** needs before its download starts: what to fetch
    and what to call it. Everything else — formats, size, the real duration — arrives when the
    entry is downloaded, exactly as it does for a URL the user pasted directly.
    """

    url: str
    title: str
    duration_seconds: float | None = None
    thumbnail_url: str | None = None

    def __post_init__(self) -> None:
        _require_text("PlaylistEntry", "url", self.url)
        _require_text("PlaylistEntry", "title", self.title)
        _require_optional_duration("PlaylistEntry", "duration_seconds", self.duration_seconds)
        _require_optional_text("PlaylistEntry", "thumbnail_url", self.thumbnail_url)


@dataclass(frozen=True, slots=True)
class MediaInfo:
    """What a probe learned about a URL — a projection of yt-dlp's `info_dict`.

    Declared fields only, for the same reason as `FormatInfo`. `T-018` pins this against
    recorded fixtures so an upstream schema change fails a test rather than a user's download.
    """

    url: str
    title: str
    formats: tuple[FormatInfo, ...] = ()

    #: A tuple, not a list: this is frozen, and a mutable default would let a caller edit a
    #: probe result that the UI is already displaying.
    duration_seconds: float | None = None
    uploader: str | None = None
    thumbnail_url: str | None = None
    is_live: bool = False

    #: Whether the probed URL is a playlist rather than a single item (`REQ-002`, `T012-R6`).
    #:
    #: Added by `T-018`. `REQ-002` requires a probe to report the distinction and `T-016`
    #: promises to display it, but no declared type could carry it: the raw `_type: "playlist"`
    #: stops at the adapter, and `ARC-002` forbids passing the dict on to find out.
    is_playlist: bool = False

    #: How many items a playlist holds, when the extractor says. `None` means unknown, not zero
    #: — a playlist whose count could not be determined is a real state, and showing "0 items"
    #: for it would be a confident lie of the kind `Job.progress` already refuses to tell.
    entry_count: int | None = None

    #: The playlist's items, when a probe enumerated them (`T-137`).
    #:
    #: **Empty is not "none"**: a playlist whose entries were not enumerated and a playlist with no
    #: items are both `()`, and `entry_count` is what tells them apart — it is what the *site*
    #: reports, while this is what this extraction materialised. `_entry_count` already keeps that
    #: distinction and this preserves it rather than collapsing the two into one number.
    entries: tuple[PlaylistEntry, ...] = ()

    #: The subtitle languages this source publishes, in the order the extractor listed them
    #: (`REQ-010`, `T-109`, `docs/UX_SPEC.md` §6's `P-17`).
    #:
    #: **Manual subtitles only, and the omission is the point.** yt-dlp keeps automatic captions
    #: in a separate map and fetches them under a separate option; offering them in the same list
    #: would let a user pick a language that `writesubtitles` alone cannot deliver, and they would
    #: get a file with no subtitles and no error. `REQ-010` names subtitles, not captions.
    #:
    #: **Empty means the probe found none, or that nothing was probed yet.** The two are told
    #: apart the same way every other optional projection is — by whether there is a `MediaInfo`
    #: at all — and the control that reads this says *"this source publishes no subtitles"*
    #: rather than drawing an empty list the user can pick nothing from.
    subtitle_languages: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text("MediaInfo", "url", self.url, "it is the url this describes")
        _require_text(
            "MediaInfo",
            "title",
            self.title,
            "when the extractor supplies none, the caller substitutes something displayable "
            "rather than storing an empty string",
        )
        # `T011-R8`, the finding that opened this task: a list of raw yt-dlp format dicts used
        # to be stored verbatim, so upstream data crossed the process boundary inside an
        # otherwise valid `Probed` message and could still mutate afterwards.
        object.__setattr__(
            self, "formats", _as_tuple_of("MediaInfo", "formats", self.formats, FormatInfo)
        )
        object.__setattr__(
            self, "entries", _as_tuple_of("MediaInfo", "entries", self.entries, PlaylistEntry)
        )
        object.__setattr__(
            self,
            "subtitle_languages",
            _as_tuple_of("MediaInfo", "subtitle_languages", self.subtitle_languages, str),
        )
        _require_optional_duration("MediaInfo", "duration_seconds", self.duration_seconds)
        _require_optional_text("MediaInfo", "uploader", self.uploader)
        _require_optional_text("MediaInfo", "thumbnail_url", self.thumbnail_url)
        _require_flag("MediaInfo", "is_live", self.is_live)
        _require_flag("MediaInfo", "is_playlist", self.is_playlist)
        _require_optional_count("MediaInfo", "entry_count", self.entry_count)
        if self.entries and not self.is_playlist:
            # Same rule as the count below, for the same reason: entries on something that is one
            # thing would be read as a playlist by anything that checks the list before the flag.
            raise ValueError(
                f"MediaInfo carries {len(self.entries)} entries on something that is not a "
                "playlist; only a playlist has entries"
            )
        if self.entry_count is not None and not self.is_playlist:
            # A count on a single item has no meaning, and a UI reading it would render "1 of 7"
            # for something that is one thing. Making the pair unrepresentable is cheaper than
            # every reader remembering to check the flag first (`T-014`'s lesson).
            raise ValueError(
                f"MediaInfo.entry_count is {self.entry_count} on something that is not a "
                "playlist; only a playlist has entries to count"
            )


@dataclass(frozen=True, slots=True)
class DownloadRequest:
    """The resolved intent for one download, frozen at job-creation time.

    `ARCHITECTURE.md` §8: settings are read into this once and never re-read. That is what
    makes a job reproducible from its request alone, and what stops a settings change from
    altering a download already in flight.

    This is the object the worker receives (`ARC-002`), so it must stay picklable and must
    contain no handles, callbacks, or live objects.
    """

    url: str
    output_directory: str
    format_selector: str
    output_template: str
    media_kind: MediaKind = MediaKind.VIDEO

    #: Tuples rather than lists throughout: a frozen dataclass with a mutable field is only
    #: shallowly frozen, and these travel between processes.
    post_processors: tuple[str, ...] = ()
    subtitle_languages: tuple[str, ...] = ()
    embed_subtitles: bool = False

    #: `REQ-010`'s chosen codec and quality. Only meaningful when `media_kind` is AUDIO.
    #:
    #: `audio_quality` is yt-dlp's `preferredquality`: either a VBR setting `0`-`9` or a target
    #: bitrate in kbps such as `192`. Kept as a string because those two vocabularies share the
    #: field upstream, and an int would silently make `0` (best VBR) mean 0 kbps.
    audio_codec: AudioCodec = AudioCodec.ORIGINAL
    audio_quality: str | None = None

    #: `REQ-010`'s remaining five, typed rather than spelled into `post_processors` (`ARC-010`).
    #:
    #: **The model widens, and that was the decision rather than the shortcut.** All five could
    #: ride in `post_processors` as yt-dlp postprocessor names, which is what that field is for and
    #: what `T-109` inherited. `ARC-010` ruled the other way for the whole application: a
    #: user-facing option is a typed, validated field, and a list of opaque strings is neither
    #: checkable by `mypy` nor visible to `PRESET_OWNED_FIELDS`'s drift test. `REQ-031`'s escape
    #: hatch — Phase 4.5, `T-184` — is where anything without a field of its own goes, on the
    #: request and past a validator, not as a raw postprocessor name.
    #:
    #: `remux_container` rewraps the streams into another container; `recode_container`
    #: re-encodes them. At most one may be set — see `_require_one_container_change`.
    remux_container: str | None = None
    recode_container: str | None = None

    #: Embed the site's thumbnail, its metadata, and its chapters into the finished file.
    #:
    #: Three flags rather than one because yt-dlp treats them as three: the thumbnail is
    #: `EmbedThumbnail` and needs the picture downloaded alongside, while metadata and chapters
    #: are two arguments to a single `FFmpegMetadata` — which is exactly the kind of shape a
    #: hand-written list of postprocessor names gets wrong. Naming that postprocessor twice, once
    #: per option, **adds** rather than loses: `FFmpegMetadata` defaults *both* arguments to
    #: `True`, so a spec that omits one turns it on, and a user asking only to keep chapter marks
    #: would find their title, uploader and source URL written into the file as well.
    #:
    #: *(This said the opposite — that the two would be deduplicated and "lose whichever flag came
    #: second". A mutation splitting them into one spec per option survived the whole suite, which
    #: is what disproved it: nothing was lost, something was added. `T109-R7` found this sibling
    #: copy still saying so after `build_postprocessors`' own docstring was corrected.)*
    embed_thumbnail: bool = False
    embed_metadata: bool = False
    embed_chapters: bool = False

    #: Network options are carried, never logged as-is. `T-038` redacts at the handler level
    #: (`NFR-007`), which is why a proxy URL may safely live in the model.
    proxy: str | None = None
    rate_limit_bytes: int | None = None
    #: Which browser's cookies to use — a **browser name**, and since `T-197` by construction
    #: rather than by intent (`REQ-026`, `DAT-003`).
    #:
    #: **`DAT-003`'s `T-049` amendment measured the gap and this closes it.** The field required
    #: only non-empty text, so `cookies_from_browser="/home/u/.mozilla/cookies.sqlite"` was
    #: accepted — a *path* travelling through a field the redaction reasoning treats as a name,
    #: into a model that is persisted. Nothing supplied one, so nothing leaked; *"none exist"*
    #: described the callers rather than an invariant. Constraining it was itself a stated
    #: reopening condition, and the 2026-08-10 amendment takes it.
    #:
    #: **A path for cookies goes in `settings.toml`, never here** — that is what keeps *"a cookie
    #: path this application supplies is never in the database"* structural.
    cookies_from_browser: str | None = None

    def __post_init__(self) -> None:
        _require_text("DownloadRequest", "url", self.url)
        _require_text("DownloadRequest", "output_directory", self.output_directory)
        _require_text(
            "DownloadRequest",
            "format_selector",
            self.format_selector,
            "an empty one silently means yt-dlp's default, which is not the preset the user chose",
        )
        _require_text("DownloadRequest", "output_template", self.output_template)
        _require_enum("DownloadRequest", "media_kind", self.media_kind, MediaKind)
        for name in ("post_processors", "subtitle_languages"):
            object.__setattr__(
                self, name, _as_tuple_of("DownloadRequest", name, getattr(self, name), str)
            )
        _require_flag("DownloadRequest", "embed_subtitles", self.embed_subtitles)
        _require_enum("DownloadRequest", "audio_codec", self.audio_codec, AudioCodec)
        _require_optional_text("DownloadRequest", "audio_quality", self.audio_quality)
        if self.audio_quality is not None and not _is_ytdlp_quality(self.audio_quality):
            raise ValueError(
                f"DownloadRequest.audio_quality must be a VBR setting 0-9 or a kbps bitrate, "
                f"not {self.audio_quality!r}; yt-dlp rejects anything else at post-processing "
                "time, which is after the download has already been paid for"
            )
        _require_container("DownloadRequest", "remux_container", self.remux_container)
        _require_container("DownloadRequest", "recode_container", self.recode_container)
        _require_one_container_change(
            "DownloadRequest", self.remux_container, self.recode_container
        )
        for flag in ("embed_thumbnail", "embed_metadata", "embed_chapters"):
            _require_flag("DownloadRequest", flag, getattr(self, flag))
        _require_optional_text("DownloadRequest", "proxy", self.proxy)
        _require_credential_free_proxy(self.proxy)
        _require_optional_text("DownloadRequest", "cookies_from_browser", self.cookies_from_browser)
        _require_browser_name("DownloadRequest", "cookies_from_browser", self.cookies_from_browser)
        _require_optional_count("DownloadRequest", "rate_limit_bytes", self.rate_limit_bytes)


@dataclass(frozen=True, slots=True)
class Preset:
    """A named, user-facing bundle that translates to a `DownloadRequest`.

    `T-010` defined the shape; built-in content and the translation live in `core/presets.py`
    (`T-015`), because deciding yt-dlp selector syntax inside a task reviewed for its domain
    model would put the two in the wrong places.

    **Every field here is a field of `DownloadRequest` under the same name.** That is the whole
    design: a preset is the subset of a request that a named choice fixes, and translation is a
    copy rather than an interpretation. `tests/unit/test_presets.py` derives that correspondence
    from both dataclasses, so a field added here and not carried across fails the suite.
    """

    name: str
    media_kind: MediaKind
    format_selector: str
    output_template: str
    post_processors: tuple[str, ...] = ()

    #: `REQ-010`'s chosen codec and quality, added by `T-015`. Without them a preset cannot say
    #: what "audio only (MP3)" means, and `REQ-006`'s two audio presets differ only in their
    #: names — which is precisely the defect `T012-R5` found one layer down, where omitting
    #: `preferredcodec` left yt-dlp's default of "keep the source codec" and the MP3 preset
    #: silently converted nothing.
    audio_codec: AudioCodec = AudioCodec.ORIGINAL
    audio_quality: str | None = None

    #: `REQ-006`'s "video with embedded subtitles" preset, likewise: `build_postprocessors`
    #: installs `FFmpegEmbedSubtitle` only when a request carries both, so a preset that cannot
    #: express them cannot ask for them.
    subtitle_languages: tuple[str, ...] = ()
    embed_subtitles: bool = False

    #: `REQ-010`'s other five, added by `T-109`. Every one of them is a field of
    #: `DownloadRequest` under the same name, which is what makes them preset-owned: a preset is
    #: the subset of a request a named choice fixes, and `PRESET_OWNED_FIELDS` derives that subset
    #: from these two dataclasses rather than from a list somebody maintains.
    remux_container: str | None = None
    recode_container: str | None = None
    embed_thumbnail: bool = False
    embed_metadata: bool = False
    embed_chapters: bool = False

    #: Built-ins ship with the application and may not be edited or deleted; user presets may.
    #: The flag lives on the preset rather than in a separate list so the UI cannot lose track
    #: of which is which.
    built_in: bool = False

    def __post_init__(self) -> None:
        _require_text("Preset", "name", self.name, "it is what the user selects it by")
        _require_text("Preset", "format_selector", self.format_selector)
        _require_enum("Preset", "media_kind", self.media_kind, MediaKind)
        _require_text("Preset", "output_template", self.output_template)
        for name in ("post_processors", "subtitle_languages"):
            object.__setattr__(self, name, _as_tuple_of("Preset", name, getattr(self, name), str))
        _require_enum("Preset", "audio_codec", self.audio_codec, AudioCodec)
        _require_optional_text("Preset", "audio_quality", self.audio_quality)
        if self.audio_quality is not None and not _is_ytdlp_quality(self.audio_quality):
            # The same rule as `DownloadRequest`, checked here too rather than only there: a
            # preset is chosen long before a request is built, and discovering the typo at
            # post-processing time costs the whole download.
            raise ValueError(
                f"Preset.audio_quality must be a VBR setting 0-9 or a kbps bitrate, "
                f"not {self.audio_quality!r}"
            )
        _require_flag("Preset", "embed_subtitles", self.embed_subtitles)
        _require_container("Preset", "remux_container", self.remux_container)
        _require_container("Preset", "recode_container", self.recode_container)
        _require_one_container_change("Preset", self.remux_container, self.recode_container)
        for flag in ("embed_thumbnail", "embed_metadata", "embed_chapters"):
            _require_flag("Preset", flag, getattr(self, flag))
        _require_flag("Preset", "built_in", self.built_in)


@dataclass(frozen=True, slots=True)
class Job:
    """One download, from queued to finished (`ARCHITECTURE.md` §5).

    Frozen, so a status change produces a new `Job` via `with_status` rather than mutating one
    that another layer may be holding. The state machine validates the change; this type just
    carries the result.
    """

    id: str
    url: str
    request: DownloadRequest
    status: JobStatus = JobStatus.QUEUED

    title: str | None = None
    output_path: str | None = None
    bytes_done: int = 0
    bytes_total: int | None = None

    #: Where the site says this job's thumbnail is (`T-117`, `REQ-002`).
    #:
    #: **A URL, not bytes.** `MediaInfo` has carried one since `T-016`; what it did not have was
    #: anywhere to live once the dialog that fetched it closed, so a queued row could show a title
    #: and never a picture. Persisted with the rest of the probe's result rather than fetched
    #: again, because the fetch is `T-119`'s problem and the address is this one's.
    #:
    #: `None` means two different things and the difference is legible from `status`: a job that
    #: has not been probed has nothing to say yet, and one that has been probed is saying the site
    #: offered no thumbnail. Neither is an error, and neither should be drawn as one.
    thumbnail_url: str | None = None

    #: Which playlist this job came from, and where it sat in it (`T-137`, `UX-005` row 9).
    #:
    #: **Denormalised on purpose — there is no playlist table.** A group has no state of its own:
    #: `UX-005` row 9a makes its chip a count of its members and row 9b makes its bar their
    #: states, so everything a group row shows is derived from the jobs below it. A table would be
    #: a second place for a title to live and nothing to keep in it, and the group would then need
    #: its own lifecycle — created before its entries, deleted after the last one, wrong in
    #: between. Three columns on the job say the same thing and cannot drift from it.
    #:
    #: All three are `None` together for a job the user pasted directly, which is the common case.
    playlist_id: str | None = None
    playlist_index: int | None = None
    playlist_title: str | None = None

    #: Whether this download is a live stream (`REQ-017`, `T-113`).
    #:
    #: **The one thing a probe can say about resumability before anything is downloaded.** An
    #: interrupted live capture has nothing to continue from — the bytes that were being served
    #: have gone — so a retry starts again by definition rather than by the server's choice. Every
    #: other case is decided at the moment of the resume by whether the server honours a `Range`
    #: request, which nothing can know in advance and which yt-dlp handles by silently starting
    #: over. `REQ-017` asks the application to *state clearly when resumption is not possible*, and
    #: this is the case where that statement is true rather than a guess.
    #:
    #: Defaults to `False` for a job written before this existed and for a playlist entry, which is
    #: named by a flat extraction and never probed (`T-137`). Both mean *nothing said it was live*,
    #: which is the honest reading: the row makes no claim rather than a wrong one.
    is_live: bool = False

    #: Who published it, and how long it is (`UX-005` §3, `T124-R4`, `REQ-002`).
    #:
    #: **The same shape and the same reasoning as `thumbnail_url`**, and they were left out of the
    #: same commit: `MediaInfo` has carried both since `T-016`, the add dialog draws both on the
    #: staging row, and neither had anywhere to live once that dialog closed — so `UX-005` §3's
    #: row anatomy could be drawn while a URL was being staged and not afterwards, on the tab the
    #: user actually watches. `T-124` narrowed §3 to `REQ-014`'s older field list rather than
    #: carrying them, and a task cannot narrow an accepted decision.
    #:
    #: `None` means the same two things it means for the thumbnail, told apart by `status`: not
    #: probed yet, or probed and the extractor named none. yt-dlp genuinely omits an uploader for
    #: some sites and a duration for a live stream, so neither absence is an error.
    uploader: str | None = None
    duration_seconds: float | None = None

    #: Failure is stored as two fields rather than a `FailureDetail`, mirroring the columns in
    #: `ARCHITECTURE.md` §5 so the persistence layer (`T-014`) is a direct mapping. The
    #: verbatim message requirement (`NFR-006`) applies here just as strongly.
    error_kind: ErrorKind | None = None
    error_message: str | None = None

    attempts: int = 0
    queue_position: int | None = None

    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_text("Job", "id", self.id)
        _require_text("Job", "url", self.url)
        _require_count("Job", "bytes_done", self.bytes_done)
        _require_optional_count("Job", "bytes_total", self.bytes_total)
        _require_count("Job", "attempts", self.attempts)
        _require_model("Job", "request", self.request, DownloadRequest)
        _require_enum("Job", "status", self.status, JobStatus)
        _require_optional_enum("Job", "error_kind", self.error_kind, ErrorKind)
        _require_optional_text("Job", "title", self.title)
        _require_optional_text("Job", "thumbnail_url", self.thumbnail_url)
        _require_optional_text("Job", "uploader", self.uploader)
        _require_optional_duration("Job", "duration_seconds", self.duration_seconds)
        _require_optional_text("Job", "playlist_id", self.playlist_id)
        _require_optional_text("Job", "playlist_title", self.playlist_title)
        _require_flag("Job", "is_live", self.is_live)
        _require_optional_count("Job", "playlist_index", self.playlist_index)
        membership = (self.playlist_id, self.playlist_index, self.playlist_title)
        if any(part is not None for part in membership) and None in membership:
            # **All three or none.** A job with an id and no index cannot be ordered within its
            # group, and one with an index and no id belongs to no group at all — both would draw
            # a group row that is missing a member or claims one it has not got. Unrepresentable
            # is cheaper than every reader checking the other two first (`T-014`'s lesson, and
            # `MediaInfo.entry_count` above is the same rule).
            raise ValueError(
                "Job carries part of a playlist membership: playlist_id, playlist_index and "
                f"playlist_title must be set together or not at all, got {membership!r}"
            )
        _require_optional_text("Job", "output_path", self.output_path)
        _require_optional_text("Job", "error_message", self.error_message)
        _require_optional_count("Job", "queue_position", self.queue_position)
        for name in ("created_at", "started_at", "finished_at"):
            _require_optional_datetime("Job", name, getattr(self, name))

    @property
    def resume_refusal(self) -> str | None:
        """Why an interrupted attempt at this job cannot be continued, or `None` (`REQ-017`).

        **Asymmetric on purpose.** `None` does not promise a resume — a server that ignores
        `Range` makes yt-dlp start from zero, and that is decided when the request is made, not
        when the row is drawn. `REQ-017` asks only for the opposite statement, and this is the one
        case a probe establishes: a live capture has nothing left to continue from.

        In words rather than as a flag, because `NFR-005` requires the row to *say* it and one
        author for the sentence is what keeps the row, its accessible text and its verb agreeing.
        """
        if not self.is_live:
            return None
        return (
            "This is a live stream, so an interrupted download starts again from the beginning "
            "rather than continuing."
        )

    def with_status(self, target: JobStatus) -> Self:
        """Return a copy in `target`, raising `IllegalTransitionError` if the move is not legal.

        Routing every status change through here is what makes `ai/TESTING.md` §7's guarantee
        real: there is no way to reach a new status that skips validation, short of building a
        `Job` by hand.
        """
        return replace(self, status=apply(self.status, target))

    def with_another_attempt(self) -> Self:
        """Return a copy whose attempt counter has advanced (`REQ-018`, `T-083`).

        **Nothing incremented this before `T-083`.** `attempts` was a schema column with a
        default that no code wrote, so every job's attempt number was `0` for life — which is
        also why `T079-R1` could not key an attempt boundary to it. Automatic retry is the first
        thing that makes it mean something, and `REQ-018`'s "the attempt count is visible" is a
        promise about this field.

        Separate from `with_status` because the two are independent: a manual retry is a status
        change the user asked for and does not spend an automatic attempt, while an automatic one
        is both.
        """
        return replace(self, attempts=self.attempts + 1)

    #: The statuses in which nothing has yet acted on the request, so replacing it is safe.
    #:
    #: `QUEUED` is a job nobody has started. `READY` is one a *probe* has resolved — the probe
    #: asked what the URL is, which is a different question from how to download it, so the
    #: download request is still open at that point.
    RETARGETABLE: ClassVar[frozenset[JobStatus]] = frozenset({JobStatus.QUEUED, JobStatus.READY})

    def with_request(self, request: DownloadRequest) -> Self:
        """Return a copy carrying `request` — legal only before a worker has acted on it.

        **The defect this exists for** (`T-075`): the add-URL dialog persists a job when the user
        probes, built from whichever preset was selected at that moment, and then started *that*
        job when the user pressed Add. Changing the preset in between updated the displayed
        selector and nothing else, so the dialog showed `bestaudio/best` while queueing a 1080p
        video request. Downloading something other than what the user selected, silently, is the
        `Critical` row of `AGENTS.md` §10's table.

        Guarded rather than a bare `replace`, for the same reason `with_status` is: the one thing
        that must never happen is retargeting a job a worker already holds, which would leave the
        stored request describing something other than what is running.
        """
        if self.status not in self.RETARGETABLE:
            # Not `IllegalTransitionError`: that one reports a move between two statuses and
            # carries both. This is a different failure — the status is not changing at all.
            raise ValueError(
                f"cannot change the request of a job in {self.status.value}; only "
                f"{', '.join(sorted(s.value for s in self.RETARGETABLE))} are still open"
            )
        return replace(self, request=request)

    def with_failure(self, kind: ErrorKind, message: str) -> Self:
        """Return a copy moved to `FAILED`, carrying the classification and the message.

        The message is stored **verbatim** (`NFR-006`, `REQ-005`). Callers that want a friendly
        summary present one alongside it; they do not substitute it here.
        """
        failed = replace(self, status=apply(self.status, JobStatus.FAILED))
        return replace(failed, error_kind=kind, error_message=message)

    @property
    def progress(self) -> float | None:
        """Fraction complete, or `None` when the total is unknown.

        `None` rather than `0.0`: a live stream and a stalled download are different states,
        and a progress bar that shows a confident zero for an unknown total is lying. The UI
        shows an indeterminate bar for `None` (`REQ-011`).
        """
        if not self.bytes_total:
            return None
        return min(self.bytes_done / self.bytes_total, 1.0)
