"""How a download says what it is, in one place for every surface (`T-159`, `REQ-009`).

## The defect this exists to stop happening a fourth time

`T140-R3` found the queue's playlist header showing `bestvideo+bestaudio/best` where its own
control, one row down, offered *Best video available* — a request named in syntax beside the same
request named in words. `T126-R2` had already fixed the ordinary row. `T-159` found the third:
**History printed `format_used` verbatim**, which is yt-dlp's answer and an *id* — `251` for
YouTube's Opus stream, or `399+140` for a merge, which is two ids joined by yt-dlp's own selector
syntax. A user reading their own download history was told a number with no explanation available
anywhere in the window.

So the project had fixed this twice and still shipped it once, and each fix was a copy of the
rule rather than a use of it. This module is the rule, and the three surfaces call it.

## It reads **what was asked for**, never the chosen preset

`T118-R8` is that mistake in the add dialog. The request is what the worker is given; anything
derived from a preset object held elsewhere is a second opinion about the download that ran. It is
also why a history record had to start carrying the asked-for format (migration `0007`) rather than
a rendered name: `audio_quality` is preset-owned, so a download converted at 320 kbps matches no
built-in, and there is no way to know that from an id.

**It takes a `FormatChoice`, which is narrower than a request, and that is a boundary rather than a
convenience** (`T159-R1`, `REQ-026`). A `DownloadRequest` also carries `cookies_from_browser`,
`proxy`, `output_directory` and `url` — none of which says what a download *is*, and the first of
which `REQ-026` forbids a durable record to hold. Handing this rule a request would have let the
record store one to feed it. `FormatChoice` is exactly `PRESET_OWNED_FIELDS`, so the rule is given
every fact it needs and no fact it must not keep. *(The record in question was History's, withdrawn
2026-08-06; the boundary outlived it — `T-176`.)*

## The MP3 bitrate, and the half of it that is still open

**It discloses the bitrate** (`T-156`): `Audio only (MP3)` converts at 192 kbps and used to say so
nowhere but in the add dialog's own control. The number is read from the choice rather than from
`MP3_QUALITY`, because `with_audio_quality` derives a preset at another bitrate and copies the name
across — a suffix taken from the constant would name a 320 kbps download 192.

**The dropdowns still offer `preset.name`, which does not carry it**, so a row reading
*Audio only (MP3), 192 kbps* sits beside a control reading *Audio only (MP3)*. That is a real gap
and it is `T140-R3`'s shape one field over. It is left open **deliberately**, on `T-156`'s own
recommendation to *"disclose first, and decide the control with `T-111`"*: what the control should
say is entangled with user presets and with `T-139`'s rule about disabling a bitrate where it does
not apply, and naming the catalogue entry `Audio only (MP3, 192 kbps)` would put 192 beside a
bitrate control set to 320 — trading this gap for a contradiction.
"""

from dataclasses import fields, replace
from typing import Final

from tracks_and_trails.core.models import AudioCodec, Preset
from tracks_and_trails.core.presets import (
    BUILT_IN_PRESETS,
    POST_PROCESSING_FIELDS,
    PRESET_OWNED_FIELDS,
    FormatChoice,
)

__all__ = ["FORMAT_PREFIX", "effective_format_text", "format_name", "preset_name_for"]

#: How a queue row states the format it is running as, once the control is gone (`UX-005` §6).
#:
#: The same three words the add dialog's row uses, so one download is described the same way in
#: the dialog that queued it and in the queue that runs it. History did not use it — a record was
#: not going to be downloaded as anything, it already had been — and History is gone (`T-176`,
#: `T-186`: the clause explaining the absence was itself in the present tense).
FORMAT_PREFIX: Final = "Download as: "

#: What each of `REQ-010`'s five adjustable options means *unset* (`T-109`).
#:
#: **Read off `Preset`'s own field defaults rather than written out here.** A second list of
#: defaults is a second opinion about what "not adjusted" is, and the two would disagree the first
#: time one of them changed — which is the drift `PRESET_OWNED_FIELDS` is derived to avoid one
#: field over.
UNADJUSTED: Final[dict[str, object]] = {
    field.name: field.default for field in fields(Preset) if field.name in POST_PROCESSING_FIELDS
}


def preset_name_for(choice: FormatChoice) -> str | None:
    """Which built-in preset describes this choice, if any.

    Matched on **every field a preset owns**, not on the format selector alone: two presets can
    share a selector and differ in the container or the output template, and naming the wrong one
    would tell the user their download is something it is not. `PRESET_OWNED_FIELDS` is derived
    from the two dataclasses, so a field added to `Preset` is compared the day it appears
    (`T015-R1`).

    `None` for a choice no built-in describes — a custom selector (`REQ-009`), or an MP3 download
    converted at a bitrate other than the preset's default, since `audio_quality` is preset-owned.
    """
    for preset in BUILT_IN_PRESETS:
        if all(getattr(preset, field) == getattr(choice, field) for field in PRESET_OWNED_FIELDS):
            return preset.name
    return None


def format_name(choice: FormatChoice) -> str:
    """What this download is, in words where there are any (`T126-R2`, `T140-R3`, `T-159`).

    **The built-in's name when one describes the request, and the literal selector otherwise.**
    `REQ-009` allows a custom selector and `retarget` is not the only thing that can set one, so a
    row whose request no built-in matches must still say what it is rather than falling silent —
    which is what "including custom selectors" costs if the text is derived from the preset list
    alone. The literal is what a user can read the syntax out of, which is `REQ-009`'s own reason
    for showing it.

    **The fallback is the selector, never the format id.** They are different things and only one
    of them was asked for: `bestaudio/best` is a request a user can recognise and act on, while
    `251` is what yt-dlp resolved it to on one site on one day.

    **The bitrate is part of the name where there is one** (`T-156`). `Audio only (MP3)` converts
    at 192 kbps and said so nowhere: the number was in `MP3_QUALITY`, in the add dialog's own
    control, and on no row. `REQ-009`'s principle is that the row says what the download actually
    is, and a name omitting the one number a user chose between is that gap one step smaller.
    """
    name = preset_name_for(choice) or _converting_preset_for(choice) or _base_preset_for(choice)
    if name is None:
        return f"{choice.format_selector}{_post_processing(choice)}"
    return f"{name}{_bitrate(choice)}{_post_processing(choice)}"


def _base_preset_for(choice: FormatChoice) -> str | None:
    """The built-in this download is **before** `REQ-010`'s adjustable options (`T-109`).

    A third describing fallback, for the same reason `_converting_preset_for` is the second: the
    two matchers above decide *identity* and must stay strict, and a user who ticks *embed
    metadata* on `Best video available` has not stopped downloading the best video available.
    Without this the row falls through to the selector and reads `bestvideo+bestaudio/best`,
    which is `T140-R3`'s defect returning through a field that did not exist when it was fixed.

    **It re-asks the existing matchers rather than adding a third rule.** The five options are
    reset and the same two functions are consulted, so there is one definition of what counts as
    a match and this cannot drift from it. Returning `None` when nothing was adjusted keeps the
    misses above meaningful: a genuinely custom selector still names itself.
    """
    plain = unadjusted(choice)
    if plain == choice:
        return None
    return preset_name_for(plain) or _converting_preset_for(plain)


def unadjusted(choice: FormatChoice) -> FormatChoice:
    """`choice` with `REQ-010`'s five adjustable options set back to their defaults.

    **Written out field by field so `mypy` checks each one**, with `UNADJUSTED` above deriving the
    same statement from `Preset`'s defaults and `tests/unit/test_format_text.py` asserting the two
    agree. A `replace(choice, **UNADJUSTED)` would be one statement instead of two and would be
    unchecked: the mapping erases to `object`, so a field whose default changed type would reach
    the constructor unexamined.
    """
    return replace(
        choice,
        remux_container=None,
        recode_container=None,
        embed_thumbnail=False,
        embed_metadata=False,
        embed_chapters=False,
    )


def _post_processing(choice: FormatChoice) -> str:
    """What `REQ-010`'s five options add to the name, and nothing when none is set (`T-109`).

    **Silence by default is what keeps every other surface unchanged.** A download that asks for
    none of these reads exactly as it did before this existed, which is why this is appended to
    the three naming routes rather than folded into them.

    Written as what happens to the file — *remuxed to mkv*, *embedding metadata* — rather than as
    the option names, because the row is telling a user what they will get. The container clause
    comes first because it is the one that changes the file's name.
    """
    parts: list[str] = []
    if choice.remux_container:
        parts.append(f"remuxed to {choice.remux_container}")
    if choice.recode_container:
        parts.append(f"recoded to {choice.recode_container}")
    embedded = [
        label
        for label, wanted in (
            ("thumbnail", choice.embed_thumbnail),
            ("metadata", choice.embed_metadata),
            ("chapters", choice.embed_chapters),
        )
        if wanted
    ]
    if embedded:
        parts.append(f"embedding {_joined(embedded)}")
    return "".join(f" · {part}" for part in parts)


def _joined(labels: list[str]) -> str:
    """`a`, `a and b`, `a, b and c` — a list a person would read aloud."""
    if len(labels) == 1:
        return labels[0]
    return f"{', '.join(labels[:-1])} and {labels[-1]}"


def _converting_preset_for(choice: FormatChoice) -> str | None:
    """The built-in this download is, **apart from its bitrate** — for naming only (`T-156`).

    **Why this is not just a looser `preset_name_for`.** That function decides *identity*: the
    queue answers `PRESET_ROLE` with it, so it is what the row's dropdown shows as selected, and
    `setData` compares against it to refuse a retarget that would change nothing. Matching a
    320 kbps download to the 192 kbps preset there would make the control claim a preset that does
    not describe the request — `T126-R4`'s defect, where a row opened its control reading a
    built-in it was not. It stays strict, and this is separate for that reason.

    **Describing is a different question from identifying, and the row is where it belongs.** A
    download converted at 320 kbps *is* "Audio only (MP3)" at 320 kbps; saying so is exactly true,
    and `_bitrate` renders the number from the choice so the sentence cannot outlive the fact. The
    alternative is what the row said before: `bestaudio/best`, which is the selector twice over and
    names nothing. `T126-R4` settled the shape — **the row speaks whenever the control cannot** —
    and this is that rule applied one field over.

    MP3 only, because `MP3_BITRATES` is MP3's scale and `with_audio_quality` refuses every other
    codec outright. A codec that wants a quality control needs its own, and should say so.
    """
    if choice.audio_codec is not AudioCodec.MP3:
        return None
    apart_from_bitrate = PRESET_OWNED_FIELDS - {"audio_quality"}
    for preset in BUILT_IN_PRESETS:
        if preset.audio_codec is not AudioCodec.MP3:
            continue
        if all(getattr(preset, field) == getattr(choice, field) for field in apart_from_bitrate):
            return preset.name
    return None


def _bitrate(choice: FormatChoice) -> str:
    """`, 192 kbps` for a download that converts at one, and nothing for a download that does not.

    **Read from the choice, never from `MP3_QUALITY`** (`T-156`). The catalogue's default and this
    download's bitrate are different questions — `with_audio_quality` derives a preset at another
    one and copies the name across — so a suffix taken from the constant would name a 320 kbps
    download 192. That is `T140-R3` exactly: a control and a row describing the same request
    differently, and it is worth more than the one character it costs to avoid.

    **Silence where there is no bitrate, rather than a zero or an "n/a"** (`T-156`'s third
    criterion). `Audio only (original)` converts nothing and `MP3_BITRATES` are MP3's scale;
    `presets.with_audio_quality` refuses the others outright, and a name implying otherwise would
    be worse than the omission this fixes.
    """
    if choice.audio_codec is not AudioCodec.MP3 or not choice.audio_quality:
        return ""
    return f", {choice.audio_quality} kbps"


def effective_format_text(choice: FormatChoice) -> str:
    """`format_name`, prefixed for the surfaces that are describing something still to happen."""
    return f"{FORMAT_PREFIX}{format_name(choice)}"
