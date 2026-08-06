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

## It reads the **request**, never the chosen preset

`T118-R8` is that mistake in the add dialog. The request is what the worker is given; anything
derived from a preset object held elsewhere is a second opinion about the download that ran. It is
also why a history record had to start carrying its request (migration `0007`) rather than a
rendered name: `audio_quality` is preset-owned, so a download converted at 320 kbps matches no
built-in, and there is no way to know that from an id.

## What it does not do yet

**It does not disclose the MP3 bitrate**, and that is `T-156`'s to decide rather than an omission
here. `Audio only (MP3)` converts at 192 kbps and says so nowhere — but the queue's format dropdown
offers `preset.name`, so a row reading *Audio only (MP3), 192 kbps* beside a control reading
*Audio only (MP3)* would be `T140-R3`'s own shape again, one field over. Disclosing it means
deciding what the **control** says too, which is the product half `T-156` holds. When that is
ruled on, this function is the one place it changes, and all three surfaces change with it.
"""

from typing import Final

from tracks_and_trails.core.models import DownloadRequest
from tracks_and_trails.core.presets import BUILT_IN_PRESETS, PRESET_OWNED_FIELDS

__all__ = ["FORMAT_PREFIX", "effective_format_text", "format_name", "preset_name_for"]

#: How a queue row states the format it is running as, once the control is gone (`UX-005` §6).
#:
#: The same three words the add dialog's row uses, so one download is described the same way in
#: the dialog that queued it and in the queue that runs it. **History does not use it** — a record
#: is not going to be downloaded as anything, it already was — so it takes `format_name` directly.
FORMAT_PREFIX: Final = "Download as: "


def preset_name_for(request: DownloadRequest) -> str | None:
    """Which built-in preset describes this request, if any.

    Matched on **every field a preset owns**, not on the format selector alone: two presets can
    share a selector and differ in the container or the output template, and naming the wrong one
    would tell the user their download is something it is not. `PRESET_OWNED_FIELDS` is derived
    from the two dataclasses, so a field added to `Preset` is compared the day it appears
    (`T015-R1`).

    `None` for a request no built-in describes — a custom selector (`REQ-009`), or an MP3 download
    converted at a bitrate other than the preset's default, since `audio_quality` is preset-owned.
    """
    for preset in BUILT_IN_PRESETS:
        if all(getattr(preset, field) == getattr(request, field) for field in PRESET_OWNED_FIELDS):
            return preset.name
    return None


def format_name(request: DownloadRequest) -> str:
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
    """
    return preset_name_for(request) or request.format_selector


def effective_format_text(request: DownloadRequest) -> str:
    """`format_name`, prefixed for the surfaces that are describing something still to happen."""
    return f"{FORMAT_PREFIX}{format_name(request)}"
