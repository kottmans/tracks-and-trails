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
    """One field a name can be built from, and how it is shown and written (`P-9`, `UX-014`)."""

    name: str
    describes: str
    #: What a user sees and types for it in the name, braces and all — `{Title}`. Empty for a field
    #: the application writes itself rather than offering (the extension).
    label: str = ""
    #: How it is written into yt-dlp's template, where that is more than `%(name)s`.
    code: str = ""

    @property
    def template_code(self) -> str:
        return self.code or f"%({self.name})s"


#: The fields this application supports, in the order Settings offers them.
#:
#: **Each one is projected from `MediaInfo`**, which is what makes the preview honest: the dialog
#: can fill it and the download's own extraction fills the same thing. `duration_string` is
#: derived by yt-dlp from `duration`, so the projection supplies the number and yt-dlp formats it —
#: one formatter, on both sides, rather than this module inventing a second one. `upload_date` is
#: formatted by yt-dlp too, from its `YYYYMMDD` into a readable date.
SUPPORTED_FIELDS: Final[tuple[TemplateField, ...]] = (
    # **Plain words, no dashes** (maintainer direction, 2026-09-13): these are read in the
    # *Add a field* menu by people who do not know what a template is.
    TemplateField("title", "The video's title", "{Title}"),
    TemplateField("uploader", "Who uploaded it (NA if the site doesn't say)", "{Uploader}"),
    TemplateField("channel", "The channel it's on (NA if the site doesn't say)", "{Channel}"),
    # **Written by the application, like *Position*** (maintainer's ruling, 2026-09-13). yt-dlp's
    # own `duration_string` is `8:27`, which a file name turns into `8-27`, the same shape as a
    # date; its strftime form always shows hours and wraps after a day. So the length the probe
    # found is written in when the download is queued, as `format_duration` spells it.
    TemplateField("duration", "How long it is, like 8m27s or 1h02m05s", "{Duration}"),
    TemplateField(
        "upload_date",
        "The day it was published, like 2026-09-13 (NA if the site doesn't say)",
        "{Upload date}",
        "%(upload_date>%Y-%m-%d)s",
    ),
    TemplateField("id", "The site's own code for the video, like jNQXAC9IVRw", "{ID}"),
    TemplateField("extractor_key", "The website it came from, like Youtube", "{Site}"),
    # **Queue-time fields** (`QUEUE_TIME_NAMES`): a playlist entry downloads as its own URL, so
    # yt-dlp never knows these. The add dialog writes them in when it queues each entry.
    TemplateField(
        "playlist_title", "The playlist's name (left out for single videos)", "{Playlist}"
    ),
    TemplateField(
        "playlist_index",
        "Its number in the playlist, like 01 (left out for single videos)",
        "{Position}",
    ),
    # **Written, never offered** (`UX-014`): every file has one, so nobody chooses it.
    TemplateField("ext", "the file extension"),
)

#: Fields no download ever sees: `resolve_queue_fields` writes them in, or takes them out, before a
#: request exists. `SUPPORTED_NAMES` leaves them out, so one that reached a request unresolved is
#: refused rather than rendered as `NA`.
QUEUE_TIME_NAMES: Final = frozenset({"playlist_title", "playlist_index", "duration"})

#: The fields a name is built from — `SUPPORTED_FIELDS` less the one the application adds itself.
OFFERED_FIELDS: Final[tuple[TemplateField, ...]] = tuple(
    field for field in SUPPORTED_FIELDS if field.label
)

SUPPORTED_NAMES: Final = frozenset(
    field.name for field in SUPPORTED_FIELDS if field.name not in QUEUE_TIME_NAMES
)

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


#: The labels a name may hold, and what each writes (`UX-014`).
_LABELLED: Final = {field.label.strip("{}").casefold(): field for field in OFFERED_FIELDS}

#: A `{Label}` in a readable name.
_LABEL: Final = re.compile(r"\{([^{}]*)\}")


def unknown_label_refusal(label: str) -> str:
    offered = ", ".join(field.label for field in OFFERED_FIELDS)
    return f"{{{label}}} is not a field this application can fill. The fields are {offered}."


def readable_to_template(name: str) -> str:
    """The yt-dlp template a readable name means: fields filled, text kept, extension added.

    **Empty means the application's own naming** and returns empty, which is what an unset
    Settings preference already stores. Text is literal — a `%` is escaped — and a `/` still makes
    a folder, as it did in a template. Raises `ValueError` naming a `{Label}` that is not a field.
    """
    if not name.strip():
        return ""
    parts: list[str] = []
    position = 0
    for match in _LABEL.finditer(name):
        parts.append(name[position : match.start()].replace("%", "%%"))
        field = _LABELLED.get(match.group(1).strip().casefold())
        if field is None:
            raise ValueError(unknown_label_refusal(match.group(1)))
        parts.append(field.template_code)
        position = match.end()
    parts.append(name[position:].replace("%", "%%"))
    return "".join(parts) + _EXTENSION_SUFFIX


#: One field group as `readable_to_template` writes it: a whole `%(…)s`, or an escaped percent.
_WRITTEN: Final = re.compile(r"%%|%\(([^)]*)\)s")


def template_to_readable(template: str) -> str | None:
    """The readable name `template` is, or `None` if it holds anything a name cannot show.

    The inverse of `readable_to_template`: every field must be an offered one written the way that
    function writes it, and the template must end in the extension it adds. A template typed
    before names existed — `%(title).30s`, say — is not a name, and is kept rather than rewritten.
    """
    if not template:
        return readable_to_template_default()
    if not template.endswith(_EXTENSION_SUFFIX):
        return None
    body = template[: -len(_EXTENSION_SUFFIX)]
    by_code = {field.template_code: field for field in OFFERED_FIELDS}
    out: list[str] = []
    position = 0
    for match in _WRITTEN.finditer(body):
        literal = body[position : match.start()]
        if "%" in literal or "{" in literal or "}" in literal:
            return None
        out.append(literal)
        if match.group(0) == "%%":
            out.append("%")
        else:
            field = by_code.get(match.group(0))
            if field is None:
                return None
            out.append(field.label)
        position = match.end()
    tail = body[position:]
    if "%" in tail or "{" in tail or "}" in tail:
        return None
    return "".join(out) + tail


#: What stands between a removed queue-time field and the text beside it. **No dot**: the dot before
#: the extension is not a separator anybody typed.
_SEPARATOR_RUN: Final = r"[ \-_,]*"

#: Where a path component ends, for a field removed from the end of one.
_COMPONENT_END: Final = r"(?=/|\.%\(ext\)s$|$)"


def format_duration(seconds: float) -> str:
    """A length as a file name should carry it: `27s`, `8m27s`, `1h02m05s`, `25h01m01s`.

    Hours only when there are any, and never wrapped at a day. Not the clock's `8:27`, which a file
    name cannot hold and which reads as a date once its colon becomes a dash.
    """
    total = max(0, round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def resolve_queue_fields(
    template: str,
    *,
    position: int | None = None,
    count: int | None = None,
    playlist: str | None = None,
    duration_seconds: float | None = None,
) -> str:
    """`template` with *Playlist*, *Position* and *Duration* written in, or taken out (`UX-014`).

    **For a playlist entry** the position is zero-padded to the playlist's own width — `01` of
    twelve, `001` of a hundred and twelve — so files sort in order, and the playlist's name is
    written as literal, folder-safe text. **For anything else** both are removed, together with the
    separator beside them, so `{Position} - {Title}` names a single video `Title` rather than
    ` - Title`. Every other field is left for yt-dlp.
    """
    from tracks_and_trails.core.paths import sanitize_component

    width = max(2, len(str(count if count is not None else position or 0)))
    values = {
        "%(playlist_index)s": f"{position:0{width}d}" if position is not None else "",
        "%(playlist_title)s": (sanitize_component(playlist).replace("%", "%%") if playlist else ""),
        "%(duration)s": format_duration(duration_seconds) if duration_seconds is not None else "",
    }
    resolved = template
    for code, value in values.items():
        if value:
            resolved = resolved.replace(code, value)
            continue
        escaped = re.escape(code)
        # Brackets that held nothing but this field go with it: `{Title} ({Position})` is `{Title}`.
        resolved = re.sub(rf"{_SEPARATOR_RUN}[(\[]{escaped}[)\]]", "", resolved)
        # At the end of a component, the separator before it goes; anywhere else, the one after.
        resolved = re.sub(rf"{_SEPARATOR_RUN}{escaped}{_COMPONENT_END}", "", resolved)
        resolved = re.sub(rf"{escaped}{_SEPARATOR_RUN}", "", resolved)
    # **A folder left with no name is no folder**: `{Playlist}/{Title}` for a single video is
    # `{Title}`, not `/{Title}` — which would read as the root and be refused as leaving the
    # download folder.
    return re.sub(r"/{2,}", "/", resolved).lstrip("/")


def settings_refusal(template: str) -> str | None:
    """`unsupported_refusal` for a Settings template, whose queue-time fields are allowed there."""
    return unsupported_refusal(resolve_queue_fields(template))


def readable_to_template_default() -> str:
    """The readable form of the application's own naming, which an empty preference means."""
    return "{Title}"


#: The one template ending a renamed file gets: yt-dlp still decides the extension (`UX-014`).
_EXTENSION_SUFFIX: Final = ".%(ext)s"

#: Why a typed name was refused when it names a folder. Folders are the setting's to decide.
NAME_SEPARATOR_REFUSAL: Final = (
    "A name can't contain / or \\. Folders come from how downloads are named in Settings."
)


def name_refusal(name: str) -> str | None:
    """Why `name` cannot be a file's name, or `None` if it can. Empty means *unset*, and is fine."""
    if "/" in name or "\\" in name:
        return NAME_SEPARATOR_REFUSAL
    return None


def renamed_template(name: str, *, within: str) -> str:
    """A template that writes the literal `name`, in the folders `within` would have used.

    **Literal, so a `%` in a name is a percent sign** — `%%` is yt-dlp's escape, and a title like
    `100% Orange Juice` would otherwise be read as a field. **The folders stay the setting's**: with
    *Uploader / Title* a renamed file still lands in its uploader's folder, because renaming one
    file is not a decision about where files go. The extension stays yt-dlp's.
    """
    refusal = name_refusal(name)
    if refusal is not None:
        raise ValueError(refusal)
    folders, separator, _file = within.rpartition("/")
    literal = name.replace("%", "%%") + _EXTENSION_SUFFIX
    return f"{folders}{separator}{literal}" if separator else literal


def renamed_name_of(template: str) -> str | None:
    """The literal name `template` writes, if `renamed_template` made it; otherwise `None`.

    Read back so a queued download that was renamed opens *Rename* on the name the user typed,
    rather than on a template. A file part that names any field — `%(` not escaped — is a pattern
    and not a rename.
    """
    _folders, _separator, file_part = template.rpartition("/")
    if not file_part.endswith(_EXTENSION_SUFFIX):
        return None
    stem = file_part[: -len(_EXTENSION_SUFFIX)]
    if re.search(r"(?<!%)(?:%%)*%\(", stem) or not stem:
        return None
    return stem.replace("%%", "%")


def path_without_extension(path: str) -> str:
    """`path` with its file's extension taken off — folders, separators and all else kept."""
    name = file_stem_of(path)
    tail = re.split(r"[\\/]", path)[-1]
    return path[: len(path) - len(tail)] + name


def file_stem_of(path: str) -> str:
    """The file name in `path`, without its folders or its extension — what *Rename* prefills.

    Both separators, because a preview path is the platform's and this module is not: a Windows
    preview has backslashes and a Linux one has slashes. Only the last dot is the extension's, since
    a title may carry dots of its own.
    """
    name = re.split(r"[\\/]", path)[-1]
    stem, dot, _extension = name.rpartition(".")
    return stem if dot else name


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
    offered = ", ".join(
        f"%({field.name})s" for field in SUPPORTED_FIELDS if field.name in SUPPORTED_NAMES
    )
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

    `duration` is the raw number; *Duration* in a name is written before a request exists
    (`resolve_queue_fields`), so nothing here formats it.
    """
    return {
        "title": media.title,
        "uploader": media.uploader,
        "duration": media.duration_seconds,
        "upload_date": media.upload_date,
        "id": media.media_id,
        "channel": media.channel,
        "extractor_key": media.site,
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
