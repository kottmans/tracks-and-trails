"""What choosing formats from the table means (`REQ-008`, `T-108`, `docs/UX_SPEC.md` §5).

**Qt-free on purpose**, like `ui/staging.py` and `ui/reveal.py`: these are the rules, and keeping
them out of `QWidget` means they are asserted directly rather than through a widget that needs a
`QApplication` and an event loop to say anything.

`REQ-008`: *allow selecting specific format IDs directly from the format table, including a separate
video and audio stream to be merged.* `UX-007` ruled `P-2` — two modes, **one format** and
**video + audio**, and in the second *"a row is chosen into whichever of the two slots its own kind
matches"*. That sentence is this module: the routing, the pair, and the selector the pair produces.

## Kind is answered from `has_video`/`has_audio`, never from a codec name

`_as_optional_codec` maps yt-dlp's explicit `'none'` **and** a missing key to `None`, so a codec
name cannot distinguish *"there is no audio here"* from *"nobody said"*. `T107-R1` is what reading
it that way cost: the table announced *audio only* for a format whose video codec was merely
unknown. `T-108` widened the projection rather than repeat the guess, because routing a row into a
slot is a claim about the stream and not about the label.

**Most formats from most sources are `UNKNOWN`, and that is the honest answer.** archive.org and
PeerTube name no codecs at all, so nothing about their formats can be classified — and a pair mode
that guessed would produce a merge request for two progressive files. `SelectionMode.PAIR` is
therefore offered but refuses what it cannot place, and says which format it could not place.

## The selector is yt-dlp's own syntax, and nothing here interprets it

A pair becomes `137+140`, a single choice becomes `137`. **`presets.with_format_selector` composes
it over whichever preset governs the row** (`T-311`), and `format_text.format_name` renders the
result — for a selector no built-in describes, that is the literal, which is what `UX_SPEC` §5
means by *"the shared naming rule's answer, not the raw selector"*: the rule is asked, and its
answer here happens to be the literal.

*(This named `presets.custom_preset`, which built a preset from **nothing** — so picking a format
discarded the row's conversion and its filename pattern, silently. `T-311` replaced that with
composition and this description was left behind; `T311-R2` is the finding.)*

**Nothing here infers a conversion from an audio-only choice**, which looks wrong and is not.
`MediaKind.AUDIO` is what installs `FFmpegExtractAudio` — it means *convert this to an audio file*,
not *this is audio*. A user who picked format `140` asked for that stream as served; adding an
extraction step would re-encode what they chose and require ffmpeg to do it.

**An explicit conversion still applies, and that is a different thing** (`T-311`, ruled
2026-09-10). The clause above is about the application *inferring* a conversion from the fact that
a chosen format carries no picture. A preset the user selected is an instruction rather than an
inference, so a row set to *Audio only (MP3)* that then picks `140` by hand converts — the streams
are what changed, and the preset composed over them is untouched.
"""

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final

from tracks_and_trails.core.models import FormatInfo

#: How yt-dlp spells "merge these two". `presets.MERGE_TOKENS` is the reading side of the same
#: fact; this is the writing side, and it is one character rather than a duplicated list.
MERGE_JOIN: Final = "+"


class FormatKind(StrEnum):
    """What a format carries, as far as the probe actually said.

    A `StrEnum` so a failure names the kind rather than an ordinal, and so the announcement
    `NFR-005` requires can be derived from it rather than written a second time beside it.
    """

    #: Video and no audio: the video half of a merge.
    VIDEO_ONLY = "video only"
    #: Audio and no video: the audio half.
    AUDIO_ONLY = "audio only"
    #: Both streams, so it needs no merging and cannot be half of one.
    COMPLETE = "video and audio"
    #: **The probe did not say**, which is not the same as any of the above and is the commonest
    #: answer for the sources this project records. Nothing may be inferred from it.
    UNKNOWN = "unknown"


class SelectionMode(StrEnum):
    """`UX-007`'s `P-2`: the table has two selection modes and no others."""

    SINGLE = "one format"
    PAIR = "video + audio"


def kind_of(entry: FormatInfo) -> FormatKind:
    """Which slot `entry` can fill, from what the projection was actually told.

    **The `'none'` is the signal, and the other side may be silent.** A format is the audio half
    when yt-dlp said there is **no video** in it; whether it also named the audio codec is a
    different question, and requiring it was wrong. A real HLS presentation is what showed this:
    an `EXT-X-MEDIA:TYPE=AUDIO` rendition comes through as `vcodec: 'none'` with **no `acodec` at
    all**, because the codec list lives on the variant rather than on the group. Requiring both
    answers made the commonest real audio half unpairable, and the criterion's own end-to-end test
    is what found it.

    **Silence alone still says nothing.** `has_audio is None` is not `False`: media.ccc.de publishes
    `vcodec: 'h264'` with no `acodec` for recordings that certainly do have sound, and reading that
    as video-only would ask yt-dlp to merge audio into a file that already has it. So a half needs
    an explicit `none` on the *other* stream — never merely an absence on its own.

    A format with `'none'` for both — a storyboard or a thumbnail track — is neither half. Both
    branches below exclude it, because *"no video"* and *"no audio"* together describe something
    that cannot be either side of a merge.
    """
    if entry.has_video is True and entry.has_audio is True:
        return FormatKind.COMPLETE
    # **Asked of the model, not restated here.** Two spellings of "is this the audio half" is two
    # places for it to drift, and the routing and the projection have to agree by construction.
    if entry.is_video_only:
        return FormatKind.VIDEO_ONLY
    if entry.is_audio_only:
        return FormatKind.AUDIO_ONLY
    # Either nothing was said, or both streams were denied. Selectable in `SINGLE` — a user may
    # genuinely want a storyboard — but it fills no slot in a merge.
    return FormatKind.UNKNOWN


class UnplaceableFormatError(ValueError):
    """A format `PAIR` mode cannot route, with the reason in words (`NFR-006`'s habit).

    Its own type so a caller can tell *"this cannot go in a slot"* from a programming error, and so
    the surface can put the message where the user is looking rather than inventing its own.
    """


@dataclass(frozen=True, slots=True)
class FormatSelection:
    """What the user has chosen so far, and what it will download as.

    **Immutable, and every transition returns a new one.** The table hands one of these to the
    dialog on every change, and a mutable object shared between them is how a surface ends up
    reading a choice that has since moved on — `T118-R14`'s shape, one object over.
    """

    mode: SelectionMode = SelectionMode.SINGLE
    #: The single choice, in `SINGLE` mode.
    single: FormatInfo | None = None
    #: The two halves, in `PAIR` mode. Either may be filled before the other.
    video: FormatInfo | None = None
    audio: FormatInfo | None = None

    @property
    def is_complete(self) -> bool:
        """Whether this selection names a download yet."""
        if self.mode is SelectionMode.SINGLE:
            return self.single is not None
        return self.video is not None and self.audio is not None

    @property
    def is_merge(self) -> bool:
        """**The user has explicitly stated a merge** — `UX_SPEC` §5's first of two facts.

        Nothing is inferred and no selector is parsed: a completed pair *is* the statement. The
        worker's gate answers the same question about the *resolved* formats and is the definitive
        one; this is what lets the dialog refuse before any bytes move (`REQ-024`).
        """
        return self.mode is SelectionMode.PAIR and self.is_complete

    def chosen(self) -> tuple[FormatInfo, ...]:
        """Every format this selection names, in the order the selector joins them."""
        if self.mode is SelectionMode.SINGLE:
            return (self.single,) if self.single is not None else ()
        return tuple(entry for entry in (self.video, self.audio) if entry is not None)

    def with_mode(self, mode: SelectionMode) -> FormatSelection:
        """Switch mode, **keeping what still means something** (`UX_SPEC` §5's `Space` key).

        Switching is not a reset: a user who picked a video-only stream and then realised they
        wanted its audio too should not have to find it again. So `SINGLE`'s choice becomes
        `PAIR`'s matching half where its kind allows, and `PAIR`'s video half becomes `SINGLE`'s
        choice on the way back.

        **What cannot survive is dropped rather than coerced.** A `COMPLETE` format has no half to
        be, and putting it in the video slot would produce `18+140` — a merge of a file that
        already has audio.
        """
        if mode is self.mode:
            return self
        if mode is SelectionMode.PAIR:
            kind = kind_of(self.single) if self.single is not None else FormatKind.UNKNOWN
            return FormatSelection(
                mode=mode,
                video=self.single if kind is FormatKind.VIDEO_ONLY else None,
                audio=self.single if kind is FormatKind.AUDIO_ONLY else None,
            )
        return FormatSelection(mode=mode, single=self.video or self.audio)

    def choose(self, entry: FormatInfo) -> FormatSelection:
        """Take `entry` into whichever slot its kind matches (`P-2`).

        In `SINGLE` mode every format is choosable, including one nothing is known about: picking a
        format id is `REQ-008`'s whole subject and the table must not refuse what yt-dlp offers.

        In `PAIR` mode only the two halves can be placed, and **the refusal names the format and
        says why** rather than doing nothing — a control that silently ignores a click is what
        `UX-005` §5 forbids and what `T-075` was.
        """
        if self.mode is SelectionMode.SINGLE:
            return replace(self, single=entry)
        kind = kind_of(entry)
        if kind is FormatKind.VIDEO_ONLY:
            return replace(self, video=entry)
        if kind is FormatKind.AUDIO_ONLY:
            return replace(self, audio=entry)
        raise UnplaceableFormatError(unplaceable_reason(entry))

    def selector(self) -> str:
        """The yt-dlp selector this selection means — `137`, or `137+140` (`REQ-008`).

        Raises rather than returning `""` for an incomplete selection: an empty selector means
        yt-dlp's *default*, not "no choice", and `DownloadRequest` refuses one for exactly that
        reason (`T-010`). A caller must ask `is_complete` first.
        """
        chosen = self.chosen()
        if not self.is_complete:
            raise ValueError(
                "this selection names no download yet; ask is_complete before selector()"
            )
        return MERGE_JOIN.join(entry.format_id for entry in chosen)

    def describe(self) -> str:
        """What is chosen, in words (`UX_SPEC` §5's keyboard path, `NFR-005`).

        *"video: 137, audio: 140"* — the spec's own wording. **Spoken rather than shown by
        highlight alone**, which is the requirement: a screen-reader user choosing the second half
        of a pair otherwise has no way to hear what the first half was.

        An empty slot says so by name. *"video: 137"* alone would read as a complete choice.
        """
        if self.mode is SelectionMode.SINGLE:
            return self.single.format_id if self.single is not None else NOTHING_CHOSEN
        return ", ".join(
            f"{label}: {entry.format_id if entry is not None else NOTHING_CHOSEN}"
            for label, entry in (("video", self.video), ("audio", self.audio))
        )


#: What an empty slot reads as. A word rather than a blank, for the reason `T118-R4` gives about
#: the inherited preset: a blank reads as *no control here* rather than as *nothing chosen yet*.
NOTHING_CHOSEN: Final = "none yet"


def unplaceable_reason(entry: FormatInfo) -> str:
    """Why `entry` cannot fill a merge slot, in the user's terms.

    Two different situations and they need different sentences, because the second is actionable
    and the first is not: a complete format is fine and simply needs no merging, while an
    unclassified one is a limit of what the site reported.
    """
    if kind_of(entry) is FormatKind.COMPLETE:
        return (
            f"Format {entry.format_id} already has both video and audio, so there is nothing to "
            f"merge. Switch to “{SelectionMode.SINGLE}” to download it on its own."
        )
    return (
        f"This source does not say whether format {entry.format_id} is video or audio, so it "
        f"cannot be paired. Switch to “{SelectionMode.SINGLE}” to download it on its own."
    )


def merge_refusal(selection: FormatSelection, *, ffmpeg_available: bool) -> str | None:
    """Why this selection cannot be committed, or `None` (`REQ-024`, `UX_SPEC` §5's first fact).

    **The first of the two ffmpeg facts, and the one that belongs to the surface.** A user who has
    explicitly chosen a video format and an audio format has *stated* a merge — nothing is inferred
    and no selector is parsed — so with ffmpeg absent that pair can be refused **before the download
    starts**, which is what `REQ-024` is explicit about. The second fact is the worker's
    `_ffmpeg_gap`, which reads the *resolved* formats and is the definitive one.

    **This is not the same check as `_will_merge` and must not become it.** `T-061` is what happens
    when a gate reads a selector instead of a decision: `bestvideo+bestaudio/best` against a source
    offering one progressive format resolves through `/best` to no merge, and the selector-reading
    gate refused it anyway. Nothing here reads a selector — it reads whether the user filled both
    slots, which is a statement rather than a prediction, so it cannot be wrong in that direction.

    Returns a sentence rather than a bool so the caller shows the reason instead of composing one:
    `NFR-006`'s habit, and the reason `UnplaceableFormatError` carries its words too.
    """
    if ffmpeg_available or not selection.is_merge:
        return None
    return (
        "Merging a separate video and audio stream needs ffmpeg, which was not found. Choose one "
        "format that already has both, or install ffmpeg."
    )


def pairable(formats: tuple[FormatInfo, ...]) -> bool:
    """Whether these formats contain a video-only **and** an audio-only stream (`P-13`'s cousin).

    `P-13` hides the merge mode when ffmpeg is absent. This is the other reason a merge may be
    impossible, and it is a property of the source rather than of the installation: archive.org,
    PeerTube and Wikimedia all publish complete files only, so *"video + audio"* on any of them is
    a mode that can never be completed.

    Kept separate from the ffmpeg question deliberately — they need different sentences, and
    collapsing them would tell a user to install ffmpeg for a source that would not merge anyway.
    """
    kinds = {kind_of(entry) for entry in formats}
    return FormatKind.VIDEO_ONLY in kinds and FormatKind.AUDIO_ONLY in kinds
