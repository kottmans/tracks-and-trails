"""The output template this application supports, and what its preview can honestly promise.

`REQ-011`, `T-112`, `docs/UX_SPEC.md` §9.1.

## Why there is a supported set at all

**`P-9`, ruled 2026-08-07:** *"The editor lists the template fields it supports beside the input,
rather than linking to yt-dlp's documentation, because the set this application supports is not
yt-dlp's whole set."*

That is not a simplification for the user's benefit. yt-dlp renders an unknown field as the literal
string `NA` and says nothing, so `%(upload_date)s` in a template silently produces `NA` in a
filename — and `REQ-011`'s preview would show `NA` too, agreeing with the write and being no help
at all. What the preview *can* be truthful about is a field this application projects, so the
supported set is exactly the set `MediaInfo` carries. Anything else is refused at edit time with
the reason (`P-23`), which is a better answer than a file called `NA`.

**Playlist fields are deliberately absent, and the reason is not squeamishness.** A playlist entry
is downloaded as an ordinary job holding its own URL (`T-137`), so the extraction that names the
file has no playlist context in it: `%(playlist_index)s` would render in the preview, where the
dialog knows the entry's position, and render as `NA` in the download, where nothing does. A field
whose preview and write disagree is the one thing this module exists to prevent.

## What the preview can promise, and where it says *intended* instead

`REQ-011` as amended (2026-08-01, `T046-R2`/`T046-R4`): the final container is frequently yt-dlp's
to choose, so the preview is **labelled as the intended path** wherever it is.

**Which requests are exact is not decided here, and deliberately so.** `T-046` already answered it:
`worker.preview_is_provisional` classifies the request and `worker.postprocessed_name` applies the
container it names, both reading yt-dlp's own `ACODECS` table. Restating either would be the second
implementation `docs/UX_SPEC.md` §9.1 forbids — and it would be the *same* mistake, since `aac` and
`alac` both landing in `m4a` is precisely what a restated table gets wrong (`T046-R4`). What lives
here is the wording and the placeholder; the classification is imported.
"""

import re
from dataclasses import dataclass
from typing import Final

from tracks_and_trails.core.models import MediaInfo


@dataclass(frozen=True, slots=True)
class TemplateField:
    """One field the editor offers, with the words it is offered in (`P-9`)."""

    name: str
    describes: str


#: The fields this application supports, in the order the editor lists them.
#:
#: **Each one is projected from `MediaInfo`**, which is what makes the preview honest: the dialog
#: can fill it and the download's own extraction fills the same thing. `duration_string` is
#: derived by yt-dlp from `duration`, so the projection supplies the number and yt-dlp formats it —
#: one formatter, on both sides, rather than this module inventing a second one.
SUPPORTED_FIELDS: Final[tuple[TemplateField, ...]] = (
    TemplateField("title", "the item's title, as the site gives it"),
    TemplateField("uploader", "who published it — `NA` where the site names nobody"),
    TemplateField("duration_string", "how long it is, as `8-27`"),
    TemplateField("ext", "the file extension"),
)

#: What `duration_string` is derived from. Supplied to the renderer, never named in a template:
#: offering both would be two spellings of one fact, and the raw number renders as `507.1`.
_DERIVED_FROM: Final = {"duration_string": "duration"}

SUPPORTED_NAMES: Final = frozenset(field.name for field in SUPPORTED_FIELDS)

#: Every `%(…)` group in a template. The **name** is whatever sits inside the parentheses; what
#: follows it is yt-dlp's conversion syntax and is none of this module's business.
_FIELD_GROUP: Final = re.compile(r"%\(([^)]*)\)")

#: Where a field name ends and yt-dlp's addressing begins.
#:
#: `%(title.30)s`, `%(formats.:.format_id)l`, `%(title,alt_title)s` and `%(title&yes|no)s` all name
#: their field first and then say something about it. Splitting on this set gives the **base**
#: names, which is what the supported set is about — and it errs towards refusing, because a base
#: name this application does not project cannot be previewed however it is addressed.
_ADDRESSING: Final = re.compile(r"[.,+&>|:]")

#: Why a preview cannot name its extension, when it cannot (`REQ-011`, amended 2026-08-01).
#:
#: **One sentence for both causes**, because `worker.preview_is_provisional` answers with one
#: boolean and that is deliberately where the classification lives. A merge and an *Audio only
#: (original)* extraction are provisional for the same reason from the user's side — yt-dlp decides
#: the container after the bytes arrive — and splitting the message here would mean re-deriving
#: which case a request is in, beside the function that already knows.
PROVISIONAL_NOTE: Final = (
    "The extension is not decided yet: yt-dlp chooses the container for this download, and it can "
    "only say which once the file has arrived."
)

#: What stands in for an extension nobody can name yet.
#:
#: A word rather than a plausible-looking `mp4`, because a plausible one is a promise and this is
#: explicitly not one. Where the request *does* decide the container, `worker.postprocessed_name`
#: replaces this with the real suffix — the same call the download's own preview makes, so the two
#: cannot disagree about which requests are exact.
UNDECIDED_EXTENSION: Final = "ext"

#: What a template must end up producing. Not a rule about syntax — an empty template renders an
#: empty path, and `safe_output_path` would refuse it far away from the field the user typed in.
EMPTY_REFUSAL: Final = "An output template cannot be empty."


def named_fields(template: str) -> tuple[str, ...]:
    """Every base field name `template` refers to, in the order it refers to them.

    Duplicates are kept: the editor's refusal names what it found, and reporting one `%(id)s` for
    three occurrences would make a template look shorter than it is to whoever is fixing it.
    """
    found: list[str] = []
    for group in _FIELD_GROUP.findall(template):
        for alternative in group.split(","):
            base = _ADDRESSING.split(alternative.strip(), maxsplit=1)[0].strip()
            if base:
                found.append(base)
    return tuple(found)


def syntax_refusal(error: str) -> str:
    """yt-dlp's own complaint about a template, framed so it says what it is about.

    Kept **verbatim inside a frame** rather than reworded. `incomplete format` on its own is what
    yt-dlp says and it is accurate; alone under a text box it reads as though the application has
    broken. `NFR-006`'s rule is about not paraphrasing away a message's content, which this does
    not — it names the subject the message is silent about.
    """
    return f"yt-dlp cannot read this template: {error}."


def unsupported_fields(template: str) -> tuple[str, ...]:
    """The fields `template` names that this application cannot fill, without repeats."""
    seen: dict[str, None] = {}
    for name in named_fields(template):
        if name not in SUPPORTED_NAMES:
            seen.setdefault(name, None)
    return tuple(seen)


def unsupported_refusal(template: str) -> str | None:
    """Why `template`'s fields are not all supported, in the words the editor shows (`P-23`)."""
    unsupported = unsupported_fields(template)
    if not unsupported:
        return None
    named = ", ".join(f"%({name})s" for name in unsupported)
    offered = ", ".join(f"%({field.name})s" for field in SUPPORTED_FIELDS)
    plural = "is not a field" if len(unsupported) == 1 else "are not fields"
    return (
        f"{named} {plural} this application can fill, so it would end up in the filename as the "
        f"word NA. The fields it supports are {offered}."
    )


def template_values(media: MediaInfo, extension: str) -> dict[str, object]:
    """The declared projection a preview renders against (`NFR-008`'s declared-fields rule).

    **`MediaInfo`, not an `info_dict`.** The raw dictionary stops at the adapter by design, and the
    parent process has never had one — so the preview is rendered from the same projection the
    staging row draws itself from, which is also what makes the two agree.

    `duration` rather than `duration_string`: yt-dlp derives the second from the first, and letting
    it do so is what keeps one formatter on both sides.
    """
    return {
        "title": media.title,
        "uploader": media.uploader,
        "duration": media.duration_seconds,
        "ext": extension,
    }


@dataclass(frozen=True, slots=True)
class OutputPreview:
    """Where one download would go, and how much of that is a promise (`REQ-011`).

    `path` is empty exactly when `refusal` is set — a refused template has no path, and showing the
    last good one beside an error is how a user comes to believe a broken template works.
    """

    path: str = ""
    #: Why this template cannot be used at all, in the words the editor shows (`P-23`).
    refusal: str | None = None
    #: Why the container may still change, when it may. `None` means the path is exact.
    provisional: str | None = None

    @property
    def is_refused(self) -> bool:
        return self.refusal is not None
