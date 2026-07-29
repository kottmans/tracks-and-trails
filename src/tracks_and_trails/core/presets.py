"""Built-in presets and the preset -> yt-dlp options translation (`REQ-006`, `REQ-009`).

## This module produces data, not yt-dlp calls

It emits format selector strings and option *values*; `downloader/ytdlp_adapter.py` turns those
into a yt-dlp options dict. That split is what keeps `core/` free of `yt_dlp`
(`ARCHITECTURE.md` §6), and the layering test enforces it. Nothing here knows whether a selector
resolves — that is yt-dlp's judgement against a real site, and pretending otherwise would mean
reimplementing its selector language in order to be wrong about it.

## One selector string, not two

`REQ-009` requires the **effective selector to be visible for every preset**, so a user can read
what a preset does and then write their own. The obvious implementation — a friendly `selector`
label beside the real one — is the one thing that must not be built: two strings maintained by
hand drift, and the one the user is shown stops being the one that runs.

So a preset has exactly one selector, `effective_selector()` returns it, and `to_request()`
copies it. There is no second string to disagree with the first.

## Translation is a copy, not an interpretation

Every field of `Preset` is a field of `DownloadRequest` under the same name
(`core/models.py`). `to_request()` therefore copies them across and adds only what a preset
cannot know: the URL and the output directory. `tests/unit/test_presets.py` derives that
correspondence from both dataclasses rather than from a list, so a preset field that stops
being carried fails the suite — this project's recurring defect is a value computed correctly
and then not acted on, and a hand-maintained copy is where that starts.

## The validation boundary

Built-in selectors are checked, once, at import: a non-string or empty one is a packaging
mistake, and it must not reach the user as a download that quietly does something else.

**A user's selector is never rejected for its content** (`REQ-009`). It is an escape hatch: a
string this project does not understand is expected, because yt-dlp understands more than this
project ever will and the syntax outlives our knowledge of it. `custom_preset()` therefore
validates nothing about what a selector *means*.

One structural limit is inherited rather than chosen here: `DownloadRequest` and `Preset` both
refuse an **empty** selector, because an empty one silently means yt-dlp's default rather than
the user's choice (`T-010`). `T-015`'s text scoped that refusal to built-ins; `T-010` had
already made it unrepresentable everywhere, and re-opening an approved model to permit an empty
selector would trade a clear error for a silent substitution.
"""

from dataclasses import fields, replace
from typing import Any, Final

from tracks_and_trails.core.models import (
    AudioCodec,
    DownloadRequest,
    MediaKind,
    Preset,
)

#: `ARCHITECTURE.md` §8 puts every output path through `core/paths.py`; this is the template
#: that gets rendered before it goes there. One constant rather than five copies, so the
#: default cannot drift between presets.
DEFAULT_OUTPUT_TEMPLATE: Final = "%(title)s.%(ext)s"

#: yt-dlp's `preferredquality` for the MP3 preset: 192 kbps, a bitrate rather than a VBR level.
#:
#: Chosen over VBR `0` ("best") because a preset named for a codec should be predictable in
#: size, and over 128 because the difference is audible on music. Overridable per request; the
#: preset states a default, it does not decide policy for anyone.
MP3_QUALITY: Final = "192"

#: The bitrates offered for MP3, highest first (`REQ-010`, `T-076`).
#:
#: Constant-bitrate values rather than yt-dlp's VBR levels `0`-`9`, for the same reason
#: `MP3_QUALITY` is: a user choosing "320" means 320 kbps, and a scale where a *lower* number is
#: better would have to be explained in the UI before it could be used.
#:
#: Stops at 128 deliberately. Below that MP3 is audibly poor for music, and a control that offers
#: a choice nobody should make is a control that has to be explained rather than read.
MP3_BITRATES: Final[tuple[str, ...]] = ("320", "256", "192", "160", "128")

#: The subtitle languages the embedded-subtitles preset asks for.
#:
#: `"all"` rather than `"en"`, deliberately: a built-in preset must not assume the user's
#: language, and "embed the subtitles that exist" is what the preset's name actually promises.
#: Narrowing it per user is a settings decision (Phase 4), not a default.
SUBTITLE_LANGUAGES: Final = ("all",)


BEST_VIDEO_1080P: Final = Preset(
    name="Best video up to 1080p (MP4)",
    media_kind=MediaKind.VIDEO,
    # **Two branches, and every one of them yields a watchable MP4.** The name promises three
    # things — video, at most 1080p, in MP4 — and a branch that delivers two of them is a
    # silent wrong result, which is the harder kind to notice.
    #
    # `T015-R1`: the original last branch was a bare `best[height<=1080]`, which selected a WebM
    # from a site with no MP4. `T015-R2`: replacing it with `bestvideo[…][ext=mp4]` selected a
    # **video-only** stream, so the preset produced a mute file. Both were the same mistake —
    # widening the fallback until *something* matches — so the fallback is gone rather than
    # widened again. What remains is a real MP4/M4A pair to merge, then a pre-muxed MP4.
    #
    # A site offering only video-only MP4 with no M4A audio now fails this preset. That is the
    # honest answer: yt-dlp reports that nothing matched, verbatim (`REQ-005`), and the user can
    # pick "best video available" or their own selector (`REQ-009`). Merging MP4 video with, say,
    # Opus audio would produce an MKV — breaking the container half of the same promise — and
    # converting instead is a post-processing decision (`REQ-010`) for a preset that says so.
    format_selector=(
        "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]"
    ),
    output_template=DEFAULT_OUTPUT_TEMPLATE,
    built_in=True,
)

BEST_VIDEO: Final = Preset(
    name="Best video available",
    media_kind=MediaKind.VIDEO,
    format_selector="bestvideo+bestaudio/best",
    output_template=DEFAULT_OUTPUT_TEMPLATE,
    built_in=True,
)

AUDIO_MP3: Final = Preset(
    name="Audio only (MP3)",
    media_kind=MediaKind.AUDIO,
    format_selector="bestaudio/best",
    output_template=DEFAULT_OUTPUT_TEMPLATE,
    # The codec is what makes this preset differ from the one below. `T012-R5`: with it
    # omitted, yt-dlp keeps the source codec and the MP3 preset converts nothing.
    audio_codec=AudioCodec.MP3,
    audio_quality=MP3_QUALITY,
    built_in=True,
)

AUDIO_ORIGINAL: Final = Preset(
    name="Audio only (original)",
    media_kind=MediaKind.AUDIO,
    format_selector="bestaudio/best",
    output_template=DEFAULT_OUTPUT_TEMPLATE,
    # `AudioCodec.ORIGINAL` carries yt-dlp's `best`, which means "no conversion" rather than
    # "the highest-quality codec". This preset extracts the audio stream as the site served it.
    audio_codec=AudioCodec.ORIGINAL,
    built_in=True,
)

VIDEO_WITH_SUBTITLES: Final = Preset(
    name="Video with embedded subtitles",
    media_kind=MediaKind.VIDEO,
    format_selector="bestvideo+bestaudio/best",
    output_template=DEFAULT_OUTPUT_TEMPLATE,
    subtitle_languages=SUBTITLE_LANGUAGES,
    embed_subtitles=True,
    built_in=True,
)

#: Every preset `REQ-006` requires, in the order the UI should offer them.
#:
#: Video first because it is the commoner case, not because it is the primary one — video and
#: audio are equal first-class citizens (`REQ-002`, `README`), and neither is the default the
#: other opts out of.
BUILT_IN_PRESETS: Final[tuple[Preset, ...]] = (
    BEST_VIDEO_1080P,
    BEST_VIDEO,
    AUDIO_MP3,
    AUDIO_ORIGINAL,
    VIDEO_WITH_SUBTITLES,
)


def check_registry(presets: tuple[Preset, ...]) -> None:
    """Refuse to ship a built-in registry that cannot mean what it says.

    Runs at import, so a mistake here fails the application rather than a download.

    **The empty and non-string selector cases are not re-checked here**, though `T-015` names
    them: `Preset` already rejects both at construction, so an unusable one cannot be built to
    be caught. Re-implementing the check would add a branch no test could reach, which reads as
    a guard while protecting nothing — `ai/TESTING.md` §13 has a whole section on that shape.
    Making the value unrepresentable is the version of this bound that holds, and it is the same
    lesson `T-014` learned about proxy credentials.

    What *is* checkable is the registry: an entry that forgot `built_in`, and two entries sharing
    a name, which would make `by_name` return whichever came first.
    """
    names: set[str] = set()
    for preset in presets:
        if not preset.built_in:
            raise ValueError(f"{preset.name!r} is in the built-in registry but is not built_in")
        if preset.name in names:
            raise ValueError(f"two built-in presets are named {preset.name!r}; a name selects one")
        names.add(preset.name)


check_registry(BUILT_IN_PRESETS)


def effective_selector(preset: Preset) -> str:
    """The selector string this preset actually downloads with (`REQ-009`).

    A function rather than a bare attribute read so that the UI has one thing to call and one
    thing to display, and so this docstring is where the "no second string" rule is stated. It
    returns the same value `to_request()` copies; there is nothing else for it to return.
    """
    return preset.format_selector


def with_audio_quality(preset: Preset, quality: str) -> Preset:
    """`preset`, converting at `quality` instead of its default (`REQ-010`, `T-076`).

    **A derived preset rather than a request override**, and the difference is `T015-R1`'s rule.
    `audio_quality` is a field both `Preset` and `DownloadRequest` declare, so it is preset-owned
    and `to_request` refuses to override it — because a request that disagrees with the preset the
    user was shown defeats `REQ-009`. Deriving a preset keeps the two in step by construction:
    what runs is what `effective_selector` and the dialog's own display describe.

    Refuses a preset that does not convert audio. "Download the video at 320 kbps" is not a
    request this application can express, and silently ignoring the number would be worse than
    saying so — the caller is the UI, and a control that appears to do nothing is the defect
    `T-075` was.
    """
    if preset.audio_codec is not AudioCodec.MP3:
        # **MP3 specifically, not "any codec that converts"** (`T076-R1`). The first version
        # gated on `CONVERTING_AUDIO_CODECS`, which is every codec but `ORIGINAL` — including
        # `FLAC`, `WAV` and `ALAC`, where a constant kbps bitrate is not a worse choice but a
        # meaningless one. `MP3_BITRATES` are MP3's scale; another codec wanting a quality
        # control needs its own, and should say so rather than inherit these.
        raise ValueError(
            f"{preset.name!r} converts to {preset.audio_codec.value}, and these bitrates are "
            f"MP3's. A quality scale for another codec is that codec's to define."
        )
    if quality not in MP3_BITRATES:
        raise ValueError(f"{quality!r} is not one of the offered bitrates {list(MP3_BITRATES)}")
    return replace(preset, audio_quality=quality)


def by_name(name: str) -> Preset:
    """The built-in preset called `name`, or `KeyError`.

    Raising rather than returning a default: a stored or restored preset name that no longer
    exists is a real disagreement between the queue and this build, and quietly substituting
    "best video" would download something the user did not ask for.
    """
    for preset in BUILT_IN_PRESETS:
        if preset.name == name:
            return preset
    raise KeyError(
        f"no built-in preset named {name!r}; available: "
        f"{', '.join(p.name for p in BUILT_IN_PRESETS)}"
    )


def custom_preset(selector: str, *, name: str = "Custom selector") -> Preset:
    """A preset carrying a **raw yt-dlp selector**, unchanged (`REQ-009`).

    The escape hatch. The string is not parsed, normalised, rewritten or judged: yt-dlp decides
    whether it resolves, and a string this project does not recognise is the expected case
    rather than the error case. Marked `built_in=False`, so the UI can tell a user's own
    selector from one that ships with the application.
    """
    return Preset(
        name=name,
        media_kind=MediaKind.VIDEO,
        format_selector=selector,
        output_template=DEFAULT_OUTPUT_TEMPLATE,
        built_in=False,
    )


#: The request fields a preset owns. Derived from the two dataclasses rather than listed, so a
#: field added to `Preset` is protected the day it appears instead of the day somebody
#: remembers this constant (`T015-R1`).
PRESET_OWNED_FIELDS: Final[frozenset[str]] = frozenset(
    {field.name for field in fields(Preset)} & {field.name for field in fields(DownloadRequest)}
)


class PresetOverrideError(ValueError):
    """An override that would make the request disagree with the preset that was shown.

    Its own type so a caller can tell this apart from a malformed value: the request is not
    invalid, it is *not the preset it claims to be*.
    """


def to_request(
    preset: Preset,
    *,
    url: str,
    output_directory: str,
    **overrides: Any,
) -> DownloadRequest:
    """Build the `DownloadRequest` this preset means, for `url` (`REQ-006`).

    Every preset field is copied under its own name; `url` and `output_directory` are the two
    things a preset cannot know. `overrides` carry the settings a preset does not fix — a proxy,
    a rate limit, a cookie source, a rate cap.

    **An override may not touch a field the preset owns** (`T015-R1`). Unrestricted overrides
    let a caller pass `format_selector="worst"` and receive exactly that while
    `effective_selector()` still displayed the preset's own string — which defeats the one thing
    `REQ-009` promises, that what is shown is what runs. Refusing is better than silently
    re-deriving the display, because a caller that wants a different selector wants
    `custom_preset()`, and saying so is more useful than quietly making it work.

    **Copied explicitly rather than by iterating the dataclass**, so mypy checks each field and
    a reader can see what a preset controls. The risk that carries — a field added and not
    copied — is covered by a test that derives the correspondence from both dataclasses instead.
    """
    owned = sorted(PRESET_OWNED_FIELDS & set(overrides))
    if owned:
        raise PresetOverrideError(
            f"{owned} belong to the preset {preset.name!r} and cannot be overridden here: the "
            "selector a user is shown must be the one that runs (REQ-009). Build a "
            "custom_preset() for a different selector, or edit the preset itself."
        )

    request = DownloadRequest(
        url=url,
        output_directory=output_directory,
        format_selector=preset.format_selector,
        output_template=preset.output_template,
        media_kind=preset.media_kind,
        post_processors=preset.post_processors,
        subtitle_languages=preset.subtitle_languages,
        embed_subtitles=preset.embed_subtitles,
        audio_codec=preset.audio_codec,
        audio_quality=preset.audio_quality,
    )
    return replace(request, **overrides) if overrides else request
