"""Sortable format lists for a probed URL (`REQ-003`, `REQ-008`, `T-107`, `T-310`).

`REQ-003`: *show the available formats for a probed URL in a sortable table (format ID, extension,
resolution, fps, codecs, bitrate, filesize/estimate, notes).* `docs/UX_SPEC.md` §4 is the surface.

**Two lists, not one grid** (`T-310`, ruled 2026-09-09 from the built window). Video on the left,
sound on the right, each carrying only the columns its own kind has. One grid forced one set of
columns, so a video-only row had to answer *audio codec* and an audio-only row had to answer
*resolution*; and one grid invited a **mode** to say which kind was being picked, which is what
refused the two formats that already carried both streams and needed no merge at all. Separate
lists need neither: nothing is routed, so nothing is refused.

Four rules shape everything here, and each exists because of a specific defect:

- **The table reads a `FormatInfo`, never a raw `info_dict` key.** `NFR-008` confines yt-dlp's
  churn to the adapter, and a widget indexing `entry["vcodec"]` puts that churn straight into
  `ui/`. `test_no_ui_module_reads_a_raw_info_dict_key` asserts it statically, the way `T-097`
  asserts the settings boundary rather than trusting a convention.
- **Sorting is over the projection, never the display string** (`UX-005`'s `T-075` lesson). `1080p`
  must sort above `720p` above `144p`, and `~12.4 MB` must sort as a number. The model answers
  `SORT_ROLE` with the underlying value and the view sorts on that role, so there is exactly one
  place the ordering can be wrong.
- **A missing field renders a word, never an empty cell and never `None`** — and **which** word
  says why it is missing (`T-305`). `UNKNOWN_TEXT` is for a value yt-dlp did not report: a live
  stream has no filesize, archive.org reports no bitrate or fps for its derivatives, and `yt-dlp
  -F` prints nothing for them either, so agreeing means showing nothing too. `ABSENT_TEXT` is for
  something yt-dlp **denied** — a format with nothing noted, or a picture on a stream declared to
  have none. The absence is information either way; saying *unknown* about a stream that was
  reported absent is a claim, and it made a table of merge candidates read as mostly unknown.
- **Every format the probe returned is in exactly one list** (`T-310`). `video_formats` and
  `audio_formats` are complements for that reason: a routing rule covering three of `FormatKind`'s
  four states would drop every unclassified format silently, and `ui/format_selection.py` records
  that *"most formats from most sources are `UNKNOWN`"*.

**The selection is a consequence, not a mode.** `FormatSelection` is unchanged and still holds both
of `P-2`'s shapes; what changed is that `FormatTable._compose` derives which one applies from what
has been picked. A format carrying both streams is the whole download; one half on its own is the
whole download too — a silent video is a legitimate thing to want — and two halves are a merge,
which is the only shape `REQ-024`'s ffmpeg refusal applies to.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtCore import (
    QPersistentModelIndex as _PersistentIndex,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFocusEvent,
    QFont,
    QKeyEvent,
    QPainter,
    QPalette,
    QPen,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.core.models import FormatInfo
from tracks_and_trails.ui import theme
from tracks_and_trails.ui.format_selection import (
    FormatKind,
    FormatSelection,
    SelectionMode,
    kind_of,
    merge_refusal,
    pairable,
)
from tracks_and_trails.ui.job_detail import UNKNOWN_TEXT, format_bytes

#: The columns `REQ-003` names, in the order it names them.
#:
#: **A tuple of headers rather than an enum of indices**, because the header text and the column
#: order are the same fact and two declarations of one fact drift. `COLUMN_COUNT` is derived.
COLUMN_HEADERS: Final = (
    "Format",
    "Ext",
    "Resolution",
    "FPS",
    "Video codec",
    "Audio codec",
    "Bitrate",
    "Size",
    "Notes",
)

#: What each list is called. **Sound rather than Audio**: the video list's own column says
#: `included`/`add one` about the same thing, and one word for one fact reads better than two.
VIDEO_LIST_TITLE: Final = "Video"
AUDIO_LIST_TITLE: Final = "Sound"

#: How surplus width is shared once each list has the width it asked for.
#:
#: **Not a proportion of the whole**, which is what these were and what made the widget's own
#: `sizeHint` a number it could not honour: a 3:2 split gave the video list 60% of whatever there
#: was, so at the widget's stated hint the wider list was still short and scrolled sideways. With
#: both lists reporting an honest hint (`FormatList.sizeHint`), the layout satisfies both first and
#: these decide only where extra room goes — and the video list, with three more columns, is where
#: extra room is worth more.
VIDEO_LIST_SHARE: Final = 3
AUDIO_LIST_SHARE: Final = 2

#: What a list's button says when the list has no current row to act on.
NOTHING_TO_CHOOSE: Final = "Nothing to choose"

#: What a list's button says, given the row it would take. `format_id` is the only field.
USE_VIDEO: Final = "Use {format_id} for the video"
USE_SOUND: Final = "Use {format_id} for the sound"
USE_COMPLETE: Final = "Use {format_id} — it has sound already"
USE_UNCLASSIFIED: Final = "Use {format_id} on its own"


#: How many rows a column samples to size itself (`T107-R6`). `ResizeToContents` otherwise asks the
#: model for every row of every column: the repaint gate measured 44,019 model reads to paint
#: fourteen visible rows of a 200-format table.
SIZING_SAMPLE: Final = 32


def says_nothing(entry: FormatInfo) -> bool:
    """Every column that could tell this row apart is empty (`T-310`).

    **Not the same question as `carries_nothing`.** That one asks whether yt-dlp *denied* both
    streams; this asks whether it said anything a person could choose on. YouTube's `233` and
    `234` are the case: real HLS audio renditions with no codec, no bitrate and no size, so the
    row reads `Unknown · Unknown · Unknown` and offers nothing to prefer it by.

    *Ruled by the maintainer on 2026-09-09 from the built window: "to the typical user those are
    just noise and additional clutter in the list."*
    """
    if entry.bitrate_kbps is not None or entry.filesize is not None:
        return False
    # **Both codecs, whatever the kind** (`T310-R6`). This branched on `kind_of` and asked an
    # `UNKNOWN` entry only about its *video* codec — so a format reporting `acodec: 'aac'` and no
    # `vcodec` at all answered *"nothing known"* and was dropped, with a codec sitting right there
    # in it. `kind_of` answers `UNKNOWN` for that entry precisely because nothing may be inferred
    # about which stream it carries, so asking a kind-shaped question of it was the error: what
    # matters here is whether *anything* was reported, not which half it belongs to.
    if entry.video_codec is not None or entry.audio_codec is not None:
        return False
    return entry.height is None


def listable(formats: Sequence[FormatInfo]) -> tuple[FormatInfo, ...]:
    """`formats` with the noise removed — **unless removing it would leave nothing**.

    Two exclusions, both ruled from the built window on 2026-09-09:

    - `carries_nothing` — yt-dlp denied both streams, so the entry is a storyboard or a thumbnail
      sheet. *"Remove the greyed out video selections. If you can't select them, why are they even
      there?"* An earlier revision listed them greyed; the maintainer's question is the better
      answer, and it removes the `flags()`, the extra word and the muted ink that listing them
      needed.
    - `says_nothing` — nothing on the row distinguishes it.

    **The guard is what makes the second exclusion safe.** `FormatInfo.is_audio_only` records that
    a real HLS `EXT-X-MEDIA:TYPE=AUDIO` rendition arrives with no codec named at all, and on a
    source served entirely over HLS those rows are the *only* audio there is. Dropping them there
    would leave a user with video and no way to get sound — so on a list where everything says
    nothing, everything stays. Noise is only noise beside signal.
    """
    kept = tuple(
        entry for entry in formats if not carries_nothing(entry) and not says_nothing(entry)
    )
    if kept:
        return kept
    return tuple(entry for entry in formats if not carries_nothing(entry))


def video_formats(formats: Sequence[FormatInfo]) -> tuple[FormatInfo, ...]:
    """Everything the video list holds: video-only, already-complete, and unclassified.

    **The complement of `audio_formats` over what `listable` keeps**, so between them every format
    worth showing appears in exactly one list. A format that belonged to neither would vanish from
    a surface `REQ-003` requires to show what the source offers, and vanishing *silently* is the
    failure this pair of functions exists to make impossible — as distinct from the two deliberate
    exclusions `listable` makes and documents.
    """
    return listable(
        tuple(entry for entry in formats if kind_of(entry) is not FormatKind.AUDIO_ONLY)
    )


def audio_formats(formats: Sequence[FormatInfo]) -> tuple[FormatInfo, ...]:
    """Everything the sound list holds: the audio halves, and nothing else."""
    return listable(tuple(entry for entry in formats if kind_of(entry) is FormatKind.AUDIO_ONLY))


#: The `Sound` column `T-310` adds, and the reason it is not one of `REQ-003`'s eight.
#:
#: `REQ-003` names what a format *is*; this names what taking it would leave you needing. It exists
#: only in the video list, where two kinds of row sit together and one of them is already finished
#: — *"if someone wants to individually select the video and audio track separately, why would they
#: pick one that had both below?"* They would not, unless the row says which it is.
SOUND_COLUMN: Final = len(COLUMN_HEADERS)

#: What the `Sound` column reads, by what the projection was told.
SOUND_INCLUDED: Final = "included"
SOUND_ADD_ONE: Final = "add one"
SOUND_NOT_STATED: Final = "not stated"


FORMAT_COLUMN: Final = 0
EXT_COLUMN: Final = 1
RESOLUTION_COLUMN: Final = 2
FPS_COLUMN: Final = 3
VIDEO_CODEC_COLUMN: Final = 4
AUDIO_CODEC_COLUMN: Final = 5
BITRATE_COLUMN: Final = 6
SIZE_COLUMN: Final = 7
NOTES_COLUMN: Final = 8

COLUMN_COUNT: Final = len(COLUMN_HEADERS)


@dataclass(frozen=True)
class Column:
    """One column of one list: which fact it shows, and what that list calls it.

    **Two names for one fact, and both are needed** (`T-310`). `field` addresses the model's own
    `_text` and `_sort_value`, which `T-107`, `T-075`, `T-305` and `T-306` all built and tested
    against the global column ids — so splitting the table into lists reuses that work rather than
    restating it. `header` is what *this* list calls it, because the same fact is called different
    things in different lists: a video's `Quality` is its resolution and a sound's `Quality` is its
    bitrate, and each list has exactly one `Codec`.
    """

    field: int
    header: str


#: The video list, and its order is the ruling (`docs/UX_SPEC.md` §4, 2026-09-09).
#:
#: **Decision, then compatibility, then provenance.** `Quality` and `Size` are what two rows are
#: compared on, so they lead — and `Quality` leads *every* list, so the eye reads down one left
#: edge rather than a different first column per list. `Bitrate`, `File type` and `ID` come last:
#: each is a fact `REQ-003` requires and none of them is why anyone clicks. `ID` is last of all,
#: which carries `T-306`'s quieter-ink ruling from emphasis into position.
VIDEO_LIST_COLUMNS: Final = (
    Column(RESOLUTION_COLUMN, "Quality"),
    Column(SOUND_COLUMN, "Sound"),
    Column(FPS_COLUMN, "FPS"),
    Column(SIZE_COLUMN, "Size"),
    Column(VIDEO_CODEC_COLUMN, "Codec"),
    Column(BITRATE_COLUMN, "Bitrate"),
    Column(EXT_COLUMN, "File type"),
    Column(NOTES_COLUMN, "Notes"),
    Column(FORMAT_COLUMN, "ID"),
)

#: The sound list. **Shorter because it asks nothing an audio stream cannot answer** — no
#: resolution, no frame rate, no video codec. That is what splitting the lists buys, and it is why
#: `no picture` and `no sound` cells no longer need to exist.
#:
#: `Quality` is the bitrate here. An audio stream's quality *is* its rate, and giving the column
#: the same name it has in the video list keeps the shared left edge the ruling asks for.
AUDIO_LIST_COLUMNS: Final = (
    Column(BITRATE_COLUMN, "Quality"),
    Column(SIZE_COLUMN, "Size"),
    Column(AUDIO_CODEC_COLUMN, "Codec"),
    Column(EXT_COLUMN, "File type"),
    Column(NOTES_COLUMN, "Notes"),
    Column(FORMAT_COLUMN, "ID"),
)

#: How thick the current section's edge is drawn, in pixels (`T202-R1`).
#:
#: Two, to match every other focused control in this application: `theme.py` thickens a bordered
#: control's border from one pixel to two when it takes the keyboard, and a header that marked the
#: same state a different thickness would be a second vocabulary for one fact.
FOCUS_EDGE: Final = 2

#: The role the view sorts on: the **projected value**, not the rendered string (`T-075`).
#:
#: A `UserRole` rather than `DisplayRole` is the whole mechanism. Qt's default sort compares what
#: `DisplayRole` returns, which is text — so `1080p` sorts below `144p` and `9.9 MB` above
#: `10.1 MB`, both of which look like the table is broken rather than like it is sorting.
SORT_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 1

#: `FormatInfo` for the current row, answered on the row's first column.
FORMAT_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 2

#: Marks a size yt-dlp estimated rather than was told (`T107-R7`, `REQ-003`'s "filesize/estimate").
#:
#: The same `~` `docs/UX_SPEC.md` §4 uses in its own example. One character, in front, so the
#: column still reads as a column of sizes.
ESTIMATE_PREFIX: Final = "~"

#: Why a pair cannot be merged here, stated where somebody assembling one will read it.
#:
#: **`P-13`'s ffmpeg sentence, and it outlived the control it was written for** (`T-310`). The
#: ruling withheld the merge *mode* when ffmpeg was absent; there is no mode now, and withholding
#: the sound list in its place would be a worse answer than the one it replaced — an audio-only
#: format is a perfectly good download and needs no ffmpeg to fetch. So both lists stay, this is
#: stated beside them, and `merge_refusal` refuses the pair itself at commit (`REQ-024`).
NO_MERGE_WITHOUT_FFMPEG: Final = (
    "Merging a separate video and audio stream needs ffmpeg, which was not found."
)
#: Why there is no sound list at all, stated in its place (`P-13`'s shape, `T-310`).
#:
#: **The ordinary case, not an edge one.** `ui/format_selection.py` records that *"most formats
#: from most sources are `UNKNOWN`"* — archive.org and PeerTube name no codecs — so a source with
#: nothing to put in a sound list is what those sites look like every time.
#:
#: Kept separate from the ffmpeg sentence for `P-13`'s own reason: telling somebody to install
#: ffmpeg for a source that would not merge anyway is advice that cannot help.
NO_MERGE_WITHOUT_A_PAIR: Final = (
    "This source offers no separate video and audio streams to merge — every format it lists "
    "carries both, or does not say."
)

#: The invalid parent every flat model is asked about, as a module-level singleton.
#:
#: A fresh `QModelIndex()` in a default argument is `B008`, and `queue_view` already solved it this
#: way — the same constant for the same reason, rather than a second spelling of it.
_ROOT: Final = QModelIndex()


def describe_resolution(entry: FormatInfo) -> str:
    """`1920x1080`, or `1080p` when only the height is known, or `UNKNOWN_TEXT`.

    Both spellings are yt-dlp's own: it reports `width` and `height` for most formats and height
    alone for some. Rendering `1080p` for a format that also knows its width would throw away a
    fact the projection carries.

    **It reads the height and nothing else, and dropping the audio-only case was the correction**
    (`T107-R1`). This used to render *audio only* whenever `FormatInfo.is_audio_only` was true —
    but that property is `video_codec is None and audio_codec is not None`, and
    `_as_optional_codec` maps both *missing* and yt-dlp's explicit `'none'` to `None`. So a format
    whose video codec is merely **unknown** was reported as having no video at all. `yt-dlp -F`
    prints `unknown` for exactly those, and the recorded-capture comparison caught the divergence.

    Saying *audio only* needs the projection to keep yt-dlp's `'none'` apart from a missing key,
    which is a widening this task did not need. Until then the table declines to assert what it
    does not know.
    """
    if entry.height is None:
        return UNKNOWN_TEXT
    if entry.width is None:
        return f"{entry.height}p"
    return f"{entry.width}x{entry.height}"


def describe_fps(fps: float | None) -> str:
    """`30`, or `29.97`, or `UNKNOWN_TEXT`.

    **Rounded for display only**, and only where rounding loses nothing: 30.0 reads as `30` and
    29.97 keeps its fraction, because 29.97 and 30 are different framerates and a table that
    showed both as `30` would be hiding the distinction a user opened it to see.
    """
    if fps is None:
        return UNKNOWN_TEXT
    return f"{fps:g}"


def describe_bitrate(kbps: float | None) -> str:
    """`1234 kbps`, or `UNKNOWN_TEXT`. Whole kbps: the fraction is below what anyone reads."""
    if kbps is None:
        return UNKNOWN_TEXT
    return f"{kbps:.0f} kbps"


def describe_size(entry: FormatInfo) -> str:
    """`44.8 MB`, or `~44.8 MB` for an estimate, or `UNKNOWN_TEXT` (`T107-R7`).

    Deliberately the same `format_bytes` the job detail uses. Two independently written byte
    formatters drift, and a user reading a size in the table and the same size on a row should not
    have to notice which is which — `format_eta`'s reasoning, one field over.

    **The tilde is the whole point of the column being named "filesize or estimate".** yt-dlp
    supplies `filesize` or `filesize_approx` depending on the extractor, and rendering both the
    same way showed a guess as a measurement. Sorting is unaffected: it is on bytes, and an
    estimate is as sortable as an exact size.
    """
    rendered = format_bytes(entry.filesize)
    if entry.filesize_is_estimate and rendered != UNKNOWN_TEXT:
        return f"{ESTIMATE_PREFIX}{rendered}"
    return rendered


#: What a cell says when yt-dlp denied the stream outright, as against never mentioning it.
ABSENT_TEXT: Final = "None"

#: Codec identifiers whose **first token alone** establishes the family, and the name for it.
#:
#: **A four-character code earns a place here only when it decides the codec by itself** (`T-306`,
#: `T306-R1`). `avc1` is always H.264 and `av01` is always AV1, whatever profile and level follow.
#: `mp4a` is **not** such a code and was in this table: it identifies MPEG-4 audio at the container
#: level and defers the codec to the object type after it, so classifying every `mp4a.*` as AAC
#: told a user selecting formats that `mp4a.69` — which is MPEG audio, layer unstated — was AAC.
CODEC_FAMILIES: Final = {
    "avc1": "H.264",
    "avc3": "H.264",
    "hev1": "H.265",
    "hvc1": "H.265",
    "vp09": "VP9",
    "vp08": "VP8",
    "av01": "AV1",
}

#: Identifiers that name a codec exactly, matched whole rather than by prefix.
#:
#: **`mp4a` entries are enumerated one object type at a time, and only where the mapping is
#: established.** `40` is the MPEG-4 audio object type indicator and the byte after it selects the
#: codec — `.2` AAC-LC, `.5` HE-AAC, `.29` HE-AACv2 — while `69` and `6b` are MPEG audio whose
#: **layer they do not state**, and `a5`/`a6` are Dolby. Anything else, `mp4a.40` object types
#: included, falls through to the raw string: **not every MPEG-4 audio object type is AAC**, and a
#: name this table cannot establish is worse than the identifier it replaced.
CODEC_NAMES: Final = {
    "h264": "H.264",
    "vp9": "VP9",
    "vp8": "VP8",
    "theora": "Theora",
    "aac": "AAC",
    "opus": "Opus",
    "vorbis": "Vorbis",
    "mp3": "MP3",
    "flac": "FLAC",
    "ac-3": "AC-3",
    "ec-3": "E-AC-3",
    "mp4a.40.2": "AAC",
    "mp4a.40.5": "HE-AAC",
    "mp4a.40.29": "HE-AAC v2",
    # **`MPEG audio`, not `MP3`** (`T306-R1`, third pass). Object type `0x69` is ISO/IEC 13818-3
    # and `0x6b` is ISO/IEC 11172-3 — MPEG-2 and MPEG-1 Part 3 — and **both cover Layers I, II
    # and III**. Naming them `MP3` assumed Layer III, so an MP2 stream was labelled MP3: the same
    # over-reading of an identifier that put every `mp4a.*` at AAC one round earlier. The family
    # is established; the layer is not, so the family is what is said.
    "mp4a.69": "MPEG audio",
    "mp4a.6b": "MPEG audio",
    "mp4a.a5": "AC-3",
    "mp4a.a6": "E-AC-3",
}


def codec_name(codec: str) -> str:
    """`avc1.640028` as `H.264`, or the string unchanged when this cannot establish the codec.

    Whole-string matches are tried before family prefixes, because the specific mapping is the
    one that carries the object type. A string neither table establishes is returned as written —
    `UX_SPEC.md` §4's raw fallback, and the behaviour `T306-R1` found missing for `mp4a`.
    """
    folded = codec.casefold()
    if folded in CODEC_NAMES:
        return CODEC_NAMES[folded]
    family = CODEC_FAMILIES.get(folded.split(".", 1)[0])
    return family if family is not None else codec


def describe_codec(codec: str | None, present: bool | None = None) -> str:
    """The codec, or **why there isn't one** — which is two different answers (`T-305`).

    `FormatInfo` carries `has_video` and `has_audio` as separate tri-state flags rather than one
    kind, because `T107-R1` cost exactly this distinction: a format whose video codec was merely
    unknown was reported as having no video at all. `present` is that flag, and the three cases
    are kept apart here rather than collapsed back into one word:

    - `False` — yt-dlp said `'none'`. There is no such stream, and `UNKNOWN_TEXT` would be a
      claim of ignorance about something it stated. Every row under *merge a separate video and
      audio stream* is this case for audio, which is what made the table read as mostly unknown.
    - `None` — yt-dlp was silent. `UNKNOWN_TEXT`, and correctly so: media.ccc.de omits `acodec`
      for recordings that certainly have sound.
    - `True`, or the caller not saying — the codec if it is named, `UNKNOWN_TEXT` if it is not.

    The module's rule that a missing field never renders as an empty cell is unchanged. This says
    which of three things is missing, not that nothing is.
    """
    if present is False:
        return ABSENT_TEXT
    return codec_name(codec) if codec else UNKNOWN_TEXT


def describe_quality(entry: FormatInfo) -> str:
    """`1080p` — the name people use for a picture (`T-310`).

    **`describe_resolution` is unchanged and still right about what it says.** It renders
    `1920x1080` where both dimensions are known, on the ground that *"rendering `1080p` for a
    format that also knows its width would throw away a fact the projection carries"*. That was
    true of a column headed *Resolution*; it is the wrong trade for one headed **Quality**, whose
    job is to distinguish rows at a glance — and on a real YouTube probe four consecutive rows
    carry `1920x1080` and the column stops distinguishing anything.

    The fact is not thrown away: the exact pixels are the cell's tool tip, which is where `T-306`
    already put the raw codec identifier for the same reason.
    """
    if entry.has_video is False:
        # An audio stream has no picture, and it is in the sound list where nothing asks. This
        # branch is for a video list holding something unclassified.
        return ABSENT_TEXT
    return f"{entry.height}p" if entry.height is not None else UNKNOWN_TEXT


def carries_nothing(entry: FormatInfo) -> bool:
    """yt-dlp **denied both streams**: a storyboard or a thumbnail track, not a download.

    **The distinction that makes this safe is `False` against `None`** (`T-310`, from the built
    window on 2026-09-09: *"there are unknown codecs for audio that have no data. Seems like we
    shouldn't even allow selecting those? Similar issue with the video selections (the mhtml files
    specifically)"*).

    `kind_of` answers `UNKNOWN` for two very different situations and this separates them:

    - **Both denied** — yt-dlp wrote `vcodec: 'none'` *and* `acodec: 'none'`. It is stating that
      the entry carries no media at all. YouTube's `mhtml` storyboards are this, and so are
      thumbnail tracks. `kind_of`'s own docstring says as much: *"a format with `'none'` for both
      — a storyboard or a thumbnail track — is neither half"*.
    - **Nothing said** — both keys absent. archive.org and PeerTube name no codecs for anything
      they publish, so **every** format they offer lands here. Those are ordinary downloads and
      refusing them would empty this surface on those sites entirely.

    Only the first is refused. Reading `kind_of(entry) is UNKNOWN` instead would refuse both, and
    the second is the commoner case by a wide margin.
    """
    return entry.has_video is False and entry.has_audio is False


def sound_group(entry: FormatInfo) -> int:
    """Which band of the video list `entry` belongs to (`T-310`, `docs/UX_SPEC.md` §4).

    `0` needs a sound half, `1` already has one, `2` the source never said. **Ruled by the
    maintainer on 2026-09-09** — *"list the video with attached audio last in the list together"* —
    and the third band follows from it rather than extending it: a format nobody classified is not
    *"video with attached audio"*, and putting it in that band would be claiming something the
    projection refuses to claim.
    """
    kind = kind_of(entry)
    if kind is FormatKind.COMPLETE:
        return 1
    if kind is FormatKind.UNKNOWN:
        return 2
    return 0


def describe_sound(entry: FormatInfo) -> str:
    """What taking this row would leave you needing (`T-310`).

    The one column `REQ-003` does not name, and the one that answers the maintainer's question:
    *"if someone wants to individually select the video and audio track separately, why would they
    pick one that had both below?"* Every row in the video list says which it is.
    """
    kind = kind_of(entry)
    if kind is FormatKind.COMPLETE:
        named = codec_name(entry.audio_codec) if entry.audio_codec else None
        return f"{SOUND_INCLUDED} · {named}" if named else SOUND_INCLUDED
    if kind is FormatKind.UNKNOWN:
        return SOUND_NOT_STATED
    return SOUND_ADD_ONE


class FormatTableModel(QAbstractTableModel):
    """Every format a probe found, one row each.

    **A table model over a frozen tuple**, not a live view of anything: a probe's formats are
    fixed once the probe ends, so there is no stream to coalesce and none of `QueueModel`'s
    repaint machinery is needed here.
    """

    #: The layout a model takes when nobody names one: every `REQ-003` column, in `REQ-003`'s
    #: order, under its own name. **`T-310` splits the surface into two lists and does not remove
    #: this**, because it is the projection's own full shape and this module's tests address it.
    DEFAULT_COLUMNS: Final = tuple(
        Column(field, header) for field, header in enumerate(COLUMN_HEADERS)
    )

    def __init__(
        self,
        formats: Sequence[FormatInfo] = (),
        parent: QObject | None = None,
        *,
        columns: Sequence[Column] | None = None,
        group_key: Callable[[FormatInfo], int] | None = None,
    ) -> None:
        super().__init__(parent)
        self._formats: tuple[FormatInfo, ...] = tuple(formats)
        #: Which facts this list shows and what it calls them (`T-310`).
        self._columns: tuple[Column, ...] = tuple(
            columns if columns is not None else self.DEFAULT_COLUMNS
        )
        #: Rows sort within their group and groups keep their order (`T-310`). `None` for no
        #: grouping, which is every list but the video one.
        self._group_key = group_key
        #: The active sort, so a reset can reapply it (`T107-R4`). `None` until something sorts.
        self._sorted_by: tuple[int, Qt.SortOrder] | None = None
        #: Format ids currently chosen, so a row can mark itself (`T-306`). The widget owns the
        #: selection; the model is only told, which keeps one place deciding what is chosen.
        self._chosen: frozenset[str] = frozenset()

    @property
    def columns(self) -> tuple[Column, ...]:
        return self._columns

    def field_of(self, column: int) -> int:
        """The global column id this list's `column` shows, for `_text` and `_sort_value`."""
        return self._columns[column].field if 0 <= column < len(self._columns) else -1

    def column_for(self, field: int) -> int:
        """Where this list shows `field`, or `-1` if it does not show it at all.

        The inverse of `field_of`, and the seam a caller needs once the same fact lives at
        different positions in different lists — `RESOLUTION_COLUMN` is column 0 of the video list
        and is absent from the sound list entirely.
        """
        for position, column in enumerate(self._columns):
            if column.field == field:
                return position
        return -1

    def set_formats(self, formats: Sequence[FormatInfo]) -> None:
        """Replace the whole table, **keeping the active sort** (`T107-R4`).

        A probe answers once, so this is a reset rather than an incremental update. What it must
        not do is install input order underneath a sort indicator that still points at a column:
        the reviewer populated a table after construction and got rows `[720, 1080]` beneath a
        *descending resolution* indicator. That is precisely the defect this module's own docstring
        warns about one paragraph over — an indicator that moves while the rows do not — recreated
        by the setter.
        """
        self.beginResetModel()
        self._formats = tuple(formats)
        if self._sorted_by is not None:
            column, order = self._sorted_by
            self._formats = self._ordered(self._formats, column, order)
        self.endResetModel()

    def formats(self) -> tuple[FormatInfo, ...]:
        return self._formats

    def rowCount(self, parent: QModelIndex | _PersistentIndex = _ROOT) -> int:
        return 0 if parent.isValid() else len(self._formats)

    def columnCount(self, parent: QModelIndex | _PersistentIndex = _ROOT) -> int:
        return 0 if parent.isValid() else len(self._columns)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ) -> object:
        if orientation is not Qt.Orientation.Horizontal:
            return None
        if role == int(Qt.ItemDataRole.DisplayRole) and 0 <= section < len(self._columns):
            return self._columns[section].header
        return None

    def data(
        self,
        index: QModelIndex | _PersistentIndex,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ) -> object:
        if not index.isValid() or not 0 <= index.row() < len(self._formats):
            return None
        entry = self._formats[index.row()]
        if role == FORMAT_ROLE:
            return entry
        if role == SORT_ROLE:
            return self._sort_value(entry, self.field_of(index.column()))
        if role == int(Qt.ItemDataRole.DisplayRole):
            return self._text(entry, self.field_of(index.column()))
        if role == int(Qt.ItemDataRole.FontRole) and entry.format_id in self._chosen:
            # **The chosen rows are marked where the choosing happens** (`T-306`). The footer
            # said *"Chosen — video: 137, audio: 140"* and nothing in the table agreed with it,
            # so a two-step selection had no running account of itself anywhere near the rows.
            font = QFont()
            font.setBold(True)
            return font
        showing_id = self.field_of(index.column()) == FORMAT_COLUMN
        if role == int(Qt.ItemDataRole.ForegroundRole) and showing_id:
            # **The identifier stays and stops leading the eye** (`T-306`, `REQ-003`). It is the
            # first column and was the strongest thing in the row, which is backwards: it is what
            # `REQ-008` selects *by* and almost never what a person is reading the row for.
            # **Read from the palette in force, not from a theme constant.** `theme.palette()`
            # sets `PlaceholderText` to the muted role for whichever palette is applied, so this
            # follows a theme switch; naming `LIGHT.muted` here would paint the light grey into
            # the dark window and nothing in this module would notice.
            return QBrush(QApplication.palette().color(QPalette.ColorRole.PlaceholderText))
        if role == int(Qt.ItemDataRole.ToolTipRole):
            if self.field_of(index.column()) == RESOLUTION_COLUMN:
                exact = describe_resolution(entry)
                return exact if exact != describe_quality(entry) else None
            # **Where the raw codec goes when the cell shows a name** (`T-306`). `REQ-009`'s
            # selector syntax and every bug report are written in `avc1.640028`, not in `H.264`,
            # so translating the cell must not put the identifier out of reach. Only the two
            # codec columns answer: a tool tip that repeated the visible text everywhere would
            # be noise, and a screen reader would read every cell twice.
            return self._raw_codec(entry, self.field_of(index.column()))
        if role == int(Qt.ItemDataRole.AccessibleTextRole):
            # **The column is named as well as the value** (`NFR-005`). A screen reader moving
            # across a row otherwise reads eight bare values with no way to tell which is the
            # bitrate and which the size — the same reason `T-060` made state text carry its own
            # label rather than relying on the header being read once.
            named = self._columns[index.column()].header
            return f"{named}: {self._text(entry, self.field_of(index.column()))}"
        return None

    def set_chosen(self, chosen: frozenset[str]) -> None:
        """Which format ids are currently picked, so the rows can say so themselves."""
        if chosen == self._chosen:
            return
        self._chosen = chosen
        if self._formats:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._formats) - 1, len(self._columns) - 1),
                [int(Qt.ItemDataRole.FontRole)],
            )

    def _raw_codec(self, entry: FormatInfo, column: int) -> str | None:
        """The codec exactly as yt-dlp reported it, for the columns that now show a name.

        **`SOUND_COLUMN` is one of them, which `T310-R5` caught.** The video list no longer shows
        an audio-codec column at all; a complete entry's audio codec is rendered *inside* the
        `Sound` cell as `included · HE-AAC`, and this method knew nothing about that column — so
        the raw `mp4a.40.5` became unreachable from the only row that shows it. `UX_SPEC` §4
        retains `T-306`'s rule that the identifier stays available, and the split moved the cell
        without moving the rule with it.
        """
        if column == VIDEO_CODEC_COLUMN and entry.video_codec:
            raw = entry.video_codec
        elif column in (AUDIO_CODEC_COLUMN, SOUND_COLUMN) and entry.audio_codec:
            raw = entry.audio_codec
        else:
            return None
        # Nothing to add where the name and the identifier are the same word.
        return raw if codec_name(raw) != raw else None

    def _text(self, entry: FormatInfo, column: int) -> str:
        """What the cell reads. **Every branch returns a non-empty string** — see `UNKNOWN_TEXT`."""
        if column == FORMAT_COLUMN:
            return entry.format_id
        if column == EXT_COLUMN:
            return entry.extension
        if column == RESOLUTION_COLUMN:
            return describe_quality(entry)
        if column == FPS_COLUMN:
            return describe_fps(entry.fps)
        if column == VIDEO_CODEC_COLUMN:
            return describe_codec(entry.video_codec, entry.has_video)
        if column == AUDIO_CODEC_COLUMN:
            return describe_codec(entry.audio_codec, entry.has_audio)
        if column == BITRATE_COLUMN:
            return describe_bitrate(entry.bitrate_kbps)
        if column == SIZE_COLUMN:
            return describe_size(entry)
        if column == NOTES_COLUMN:
            # **A note nobody wrote is not a fact nobody knows** (`T-305`). yt-dlp's `format_note`
            # is free prose it supplies when it has something to add; its absence says there was
            # nothing to add, and claiming ignorance of it made a third of this table read as
            # unknown when only the size column ever was.
            return entry.note or ABSENT_TEXT
        if column == SOUND_COLUMN:
            return describe_sound(entry)
        return UNKNOWN_TEXT

    def _sort_value(self, entry: FormatInfo, column: int) -> tuple[float, str]:
        """The key the column sorts by — the projection, never the rendered text (`T-075`).

        **Always a `(number, text)` pair, for every column, so the comparison is total.** A column
        that returned a bare `int` for some rows and a `str` for others raises `TypeError` the
        moment `sorted` compares them, and format ids are exactly that column: `137` and
        `hls-1080` both occur. The pair sorts numerically first and settles ties on text, so one
        shape covers both kinds of column and there is no branch that can produce an
        uncomparable pair.

        **A missing value sorts as `-1`**, which puts every unknown at one end of a numeric column
        rather than interleaving them. Text sorts case-insensitively: `AVC1` above `avc1` is an
        ordering a user reads as random.
        """
        if column == FORMAT_COLUMN:
            # Format ids are *mostly* numeric and not reliably so — `137`, but also `hls-1080`.
            # Numeric ids sort numerically (so `9` precedes `137` rather than following it) and
            # named ones sort after all of them, on text.
            if entry.format_id.isdigit():
                return (float(entry.format_id), "")
            return (float("inf"), entry.format_id.casefold())
        if column == EXT_COLUMN:
            return (0.0, entry.extension.casefold())
        if column == RESOLUTION_COLUMN:
            # **Height, not the rendered string.** This is the column `T-075` is about: `1080p`
            # text-sorts below `144p`, and an audio-only row has no height at all.
            return (float(entry.height) if entry.height is not None else -1.0, "")
        if column == FPS_COLUMN:
            return (entry.fps if entry.fps is not None else -1.0, "")
        if column == VIDEO_CODEC_COLUMN:
            # **Ordered by the name the cell shows** (`T-306`), with the identifier
            # breaking ties, so every `H.264` sorts together however yt-dlp spelled
            # it. Still the projection rather than the display string: the value is
            # derived here, not read back out of the view.
            raw = entry.video_codec or ""
            return (0.0, f"{codec_name(raw).casefold()}\x00{raw.casefold()}")
        if column == AUDIO_CODEC_COLUMN:
            # **Ordered by the name the cell shows** (`T-306`), with the identifier
            # breaking ties, so every `H.264` sorts together however yt-dlp spelled
            # it. Still the projection rather than the display string: the value is
            # derived here, not read back out of the view.
            raw = entry.audio_codec or ""
            return (0.0, f"{codec_name(raw).casefold()}\x00{raw.casefold()}")
        if column == BITRATE_COLUMN:
            return (entry.bitrate_kbps if entry.bitrate_kbps is not None else -1.0, "")
        if column == SIZE_COLUMN:
            # **Bytes, not "12.4 MB".** The other half of `T-075`: `9.9 MB` text-sorts above
            # `10.1 MB`, and an estimate and an exact size are both just numbers here.
            return (float(entry.filesize) if entry.filesize is not None else -1.0, "")
        if column == NOTES_COLUMN:
            return (0.0, (entry.note or "").casefold())
        if column == SOUND_COLUMN:
            # The group, then the word — so sorting this column orders *finished, needs a half,
            # nothing stated* rather than alphabetising three unrelated phrases.
            return (float(sound_group(entry)), describe_sound(entry).casefold())
        return (0.0, "")

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        """Reorder the rows by `column`, on `_sort_value` (`T-075`).

        **Implemented here rather than left to Qt.** `QTableView.setSortingEnabled(True)` calls
        this method; the default `QAbstractItemModel.sort` does nothing, so a table that merely
        enables sorting shows a sort indicator that moves and rows that do not. That is worse than
        no sorting at all — it looks like it worked.

        A `QSortFilterProxyModel` with `setSortRole` is the other idiom and was not used: it would
        put the ordering behind Qt's `QVariant` comparison of whatever `SORT_ROLE` returns, and the
        keys here are Python tuples. Sorting them in Python is one line and leaves nothing to
        infer about how two variants compare.
        """
        if not 0 <= column < len(self._columns):
            return
        self.layoutAboutToBeChanged.emit()
        # **Persistent indexes are remapped, which is what keeps a selection on its own row**
        # (`T107-R4`). Qt tracks a current row by index, so a sort that only replaces the tuple
        # leaves the *row number* selected and silently changes which format that is — the
        # reviewer selected `b`, sorted, and `current_format()` answered `a`. Anything holding a
        # `QPersistentModelIndex` — the view's current index among them — follows its row here.
        old_indexes = self.persistentIndexList()
        before = list(self._formats)
        self._formats = self._ordered(self._formats, column, order)
        self._sorted_by = (column, order)
        moved = {id(entry): row for row, entry in enumerate(self._formats)}
        self.changePersistentIndexList(
            old_indexes,
            [
                self.index(moved[id(before[index.row()])], index.column())
                if 0 <= index.row() < len(before)
                else QModelIndex()
                for index in old_indexes
            ],
        )
        self.layoutChanged.emit()

    def _ordered(
        self, formats: tuple[FormatInfo, ...], column: int, order: Qt.SortOrder
    ) -> tuple[FormatInfo, ...]:
        """`formats` in `column` order, **then grouped**. One implementation, so `sort` and a
        reset cannot differ.

        **Two passes, and Python's stable sort is what makes the second one correct** (`T-310`).
        The maintainer ruled that formats already carrying sound *"list … last in the list
        together"*, and a compound key of `(group, column_value)` cannot express that: `reverse`
        applies to the whole key, so any descending sort would float the group to the **top** —
        the opposite of the ruling. Sorting by the column first and then by the group alone leaves
        the column's order intact inside each group.
        """
        ordered = sorted(
            formats,
            key=lambda entry: self._sort_value(entry, self.field_of(column)),
            reverse=order is Qt.SortOrder.DescendingOrder,
        )
        if self._group_key is not None:
            ordered.sort(key=self._group_key)
        return tuple(ordered)


class SortableHeader(QHeaderView):
    """The table's header, with a **current section the keyboard can move** (`T107-R3`).

    `QHeaderView` has no notion of a current section — it is a strip of labels a pointer clicks.
    So an event filter that made a focused header react to `Space` still sorted whatever the
    indicator already pointed at, and there was no way to choose a different column. The reviewer's
    words: *a focused section that the user cannot select is not a keyboard-operable header*.

    A subclass rather than more event filtering, because this needs to **paint** the current
    section as well as track it. `NFR-005` forbids conveying state by colour alone, and a focus
    rectangle a user cannot see is the same defect one sense over.
    """

    #: `column` — the user asked for this column to be sorted.
    sort_requested = Signal(int)

    def __init__(self, orientation: Qt.Orientation, parent: QWidget | None = None) -> None:
        super().__init__(orientation, parent)
        self._current = 0
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSectionsClickable(True)

    def current_section(self) -> int:
        return self._current

    def set_current_section(self, section: int) -> None:
        if not 0 <= section < max(self.count(), 1):
            return
        self._current = section
        # **Announced, not only drawn** (`NFR-005`). A screen-reader user moving along the header
        # otherwise hears nothing change, and the sort they trigger lands on a column they were
        # never told they were on.
        self.setAccessibleDescription(f"{COLUMN_HEADERS[section]}, press Space to sort")
        self.updateSection(section)
        self.viewport().update()

    def paintSection(
        self,
        painter: QPainter,
        rect: QRect,
        logicalIndex: int,  # noqa: N803 - Qt's name
    ) -> None:
        super().paintSection(painter, rect, logicalIndex)
        if not (self.hasFocus() and logicalIndex == self._current):
            return
        # **Drawn here rather than asked of `PE_FrameFocusRect`** (`T202-R1`, third round). That
        # primitive is the style's idea of a focus rectangle, and once a style sheet is installed
        # the style is `QStyleSheetStyle`, whose idea of one is a hairline that barely differs from
        # the header strip it sits on. Measured on the rendered header: **zero** pixels changed by
        # 3:1 or more when this section took the keyboard, in both palettes — the whole-application
        # sweep in `tests/ui/test_colour_is_never_alone.py` is what found it, and this class's own
        # docstring had already named the defect it is: *a focus rectangle a user cannot see is the
        # same defect one sense over*.
        #
        # `accent` at two pixels, which is the same shape and the same colour every other focused
        # control in this application takes, and it sits **4.61:1** against the header strip in
        # light and **7.78:1** in dark — over the 3:1 `theme.MINIMUM_CONTROL_CONTRAST` asks of an
        # edge. `theme.applied()` for the colour, as `ui/row_delegate.py` does for the same reason:
        # a painter cannot read a style sheet.
        painter.save()
        painter.setPen(QPen(QColor(theme.applied().accent), FOCUS_EDGE))
        # Inset by half the pen, so a two-pixel stroke lands inside the section rather than
        # straddling its boundary and being clipped to one pixel.
        painter.drawRect(rect.adjusted(1, 1, -FOCUS_EDGE, -FOCUS_EDGE))
        painter.restore()

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Arrive on the column the table is sorted by, which is the one the user last acted on."""
        super().focusInEvent(event)
        indicated = self.sortIndicatorSection()
        self.set_current_section(indicated if 0 <= indicated < self.count() else 0)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """`←` `→` choose a column; `Space` or `Enter` sorts it (`docs/UX_SPEC.md` §4).

        **`Tab` is deliberately not handled**, so it falls through to Qt's focus traversal and
        leaves the header. A widget that swallowed `Tab` would trap a keyboard user on it.
        """
        key = event.key()
        if key == int(Qt.Key.Key_Left):
            self.set_current_section(self._current - 1)
            return
        if key == int(Qt.Key.Key_Right):
            self.set_current_section(self._current + 1)
            return
        if key in (int(Qt.Key.Key_Space), int(Qt.Key.Key_Return), int(Qt.Key.Key_Enter)):
            self.sort_requested.emit(self._current)
            return
        super().keyPressEvent(event)


class FormatList(QWidget):
    """One kind's formats: a heading, a sortable list, and the one button that takes a row.

    **The unit `T-310` splits the table into.** Each list carries only the columns its kind has —
    a video list never asks a video for its audio codec, a sound list never asks an audio stream
    for its resolution — which is what removes the `no sound` and `no picture` cells that a single
    shared grid made unavoidable.

    A widget rather than a bare `QTableView` because the heading and the button are part of what
    makes it a list rather than a pane: `UX-005` §5 forbids a control that silently does nothing,
    and a button whose words change with the current row is how this surface says what taking that
    row would do.
    """

    #: `FormatInfo` — the user took this row from this list.
    chosen = Signal(object)

    def __init__(
        self,
        title: str,
        formats: Sequence[FormatInfo],
        columns: Sequence[Column],
        *,
        verb: Callable[[FormatInfo], str],
        parent: QWidget | None = None,
        group_key: Callable[[FormatInfo], int] | None = None,
        sort_column: int = 0,
    ) -> None:
        super().__init__(parent)
        self._verb = verb
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._title = QLabel(title, self)
        self._title.setObjectName("formatListTitle")
        heading_font = QFont(self._title.font())
        heading_font.setBold(True)
        self._title.setFont(heading_font)
        layout.addWidget(self._title)

        self._model = FormatTableModel(formats, self, columns=columns, group_key=group_key)
        self._view = QTableView(self)
        self._view.setObjectName("formatListView")
        self._view.setModel(self._model)
        self._view.setSortingEnabled(True)
        self._view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._view.setAccessibleName(title)
        self._view.verticalHeader().setVisible(False)
        # `Tab` must leave the list rather than walk its cells — `T107-R3`, unchanged by the split.
        self._view.setTabKeyNavigation(False)

        header = SortableHeader(Qt.Orientation.Horizontal, self._view)
        self._view.setHorizontalHeader(header)
        header.sort_requested.connect(self.sort_by)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setResizeContentsPrecision(SIZING_SAMPLE)
        header.setSortIndicatorShown(True)
        header.setAccessibleName(f"Sort {title.lower()} by column")
        self._header = header
        layout.addWidget(self._view)

        self._button = QPushButton(self)
        self._button.setObjectName("formatListChoose")
        self._button.clicked.connect(self.choose_current)
        layout.addWidget(self._button, 0, Qt.AlignmentFlag.AlignLeft)

        # `Enter` or a double-click still chooses, and now there is a visible control that says so
        # (`docs/UX_SPEC.md` §4's keyboard row, and the maintainer's 2026-09-09 finding that the
        # gesture was the only route in).
        self._view.activated.connect(lambda _index: self.choose_current())

        self._view.sortByColumn(sort_column, Qt.SortOrder.DescendingOrder)
        self._select_first_row()
        self._view.selectionModel().currentRowChanged.connect(lambda *_a: self._relabel())
        self._relabel()

    # Qt's override name, hence the camelCase.
    def sizeHint(self) -> QSize:
        """Wide enough for the columns, and tall enough for the rows (`T-310`).

        **`QTableView.sizeHint()` is a fixed default and says nothing about the content.** It
        answers about 256px whatever is in the model, so a list of eight sized columns reported a
        width less than half of what it needed — and `AddUrlDialog._widen_for`, which asks the
        panel how much room to make, would have widened the dialog to a number with no relationship
        to the table inside it. Measured on 2026-09-09: the widget hinted **518px** for a surface
        that first renders without truncation at **1060px**.

        `sizeHintForColumn` is the view's own answer to *how wide must this column be for its
        contents*, which is the same question `ResizeToContents` asks — so this reports what the
        layout will actually produce rather than a second opinion about it.
        """
        base = super().sizeHint()
        # **`header.length()`, not a sum of cell hints.** `ResizeToContents` sizes each section to
        # the wider of its content and its own *label*, and on this table the labels usually win —
        # `Quality`, `File type` and `Bitrate` are all longer than the values under them. Summing
        # `sizeHintForColumn` alone reported 408px for a video list whose header measures 628px,
        # and the 220px difference was entirely headings. `length()` is the header's own total and
        # is stable before the widget is ever shown, which is when the dialog asks.
        header = self._view.horizontalHeader()
        columns = max(
            header.length(),
            sum(
                max(self._view.sizeHintForColumn(column), header.sectionSizeHint(column))
                for column in range(self._model.columnCount())
            ),
        )
        # **Room for the vertical scrollbar, whether or not one is showing.** A probe with more
        # formats than fit puts one there, and a width measured without it is a width that starts
        # scrolling sideways the moment the list gets long — which is exactly the case a format
        # table is for. Measured at 35px short across all three font sizes without this, on a
        # widget with two lists.
        chrome = 2 * self._view.frameWidth() + self._view.verticalScrollBar().sizeHint().width()

        # **The height is the same defect one axis over, and the maintainer found it in the built
        # window**: *"there is a ton of whitespace underneath the audio/video selections, but you
        # have to scroll to select them."* `AddUrlDialog.panel_height_for` gives the open row
        # `min(panel.sizeHint().height(), available)` — so a view reporting Qt's fixed default
        # asked for 366px of a 520px row, and the difference was drawn as empty space beneath a
        # list that was scrolling. Asking for the rows it has lets the panel's own cap decide.
        # **Every row, uncapped, and the cap this replaces is why.** A sixteen-row limit still
        # left the maintainer's complaint intact — 42px of empty panel beneath a list showing
        # fifteen of eighteen formats — because a cap bites in exactly the case the complaint is
        # about. `panel_height_for` already clamps this to the room the staging list has, so
        # asking for everything cannot make the row too tall; it can only stop it being too short
        # while there is room going spare. A two-hundred-format probe asks for an absurd number
        # and is given the viewport, which is the right answer to both.
        rows = self._model.rowCount()
        # **`defaultSectionSize`, not `sizeHintForRow`.** The view draws its rows at the vertical
        # header's section size — 30px under this application's style sheet — while
        # `sizeHintForRow` answers 18px, the bare text height with none of the sheet's padding.
        # Sizing on the smaller number asked for two thirds of the height the rows actually take,
        # which left the panel scrolling with room to spare and looked correct in the source.
        row_height = max(
            self._view.verticalHeader().defaultSectionSize(),
            self._view.sizeHintForRow(0) if rows else 0,
        )
        wanted = (
            self._view.horizontalHeader().sizeHint().height()
            + rows * row_height
            + 2 * self._view.frameWidth()
        )
        height = base.height() + max(0, wanted - self._view.sizeHint().height())
        return QSize(max(base.width(), columns + chrome), max(base.height(), height))

    @property
    def view(self) -> QTableView:
        return self._view

    @property
    def model(self) -> FormatTableModel:
        return self._model

    @property
    def header(self) -> SortableHeader:
        return self._header

    @property
    def button(self) -> QPushButton:
        return self._button

    def set_formats(self, formats: Sequence[FormatInfo]) -> None:
        self._model.set_formats(formats)
        self._select_first_row()
        self._relabel()

    def set_chosen(self, chosen: frozenset[str]) -> None:
        self._model.set_chosen(chosen)

    def current_format(self) -> FormatInfo | None:
        index = self._view.currentIndex()
        if not index.isValid():
            return None
        carried = self._model.data(index, FORMAT_ROLE)
        return carried if isinstance(carried, FormatInfo) else None

    def choose_current(self) -> None:
        """Report the current row. **Nothing is refused** (`T-310`, `docs/UX_SPEC.md` §5)."""
        entry = self.current_format()
        if entry is not None:
            self.chosen.emit(entry)

    def sort_by(self, column: int) -> None:
        """Sort by `column`, reversing if it is already the sorted one (`docs/UX_SPEC.md` §4).

        The one place the "again reverses" rule lives, so the header click and the key press
        cannot disagree about it.
        """
        if not 0 <= column < len(self._model.columns):
            return
        current = self._header.sortIndicatorSection()
        ascending = Qt.SortOrder.AscendingOrder
        descending = Qt.SortOrder.DescendingOrder
        if current == column and self._header.sortIndicatorOrder() is ascending:
            order = descending
        else:
            order = ascending
        self._view.sortByColumn(column, order)

    def _relabel(self) -> None:
        entry = self.current_format()
        self._button.setEnabled(entry is not None)
        self._button.setText(self._verb(entry) if entry is not None else NOTHING_TO_CHOOSE)

    def _select_first_row(self) -> None:
        """Give the list a current row as soon as it has one (`T-152`, `docs/UX_SPEC.md` §4).

        **A declared keyboard route that needs a click first is not one.** Every listed row can be
        chosen — `listable` removes the ones that could not — so row zero is always a valid place
        to open on.
        """
        if self._model.rowCount():
            self._view.setCurrentIndex(self._model.index(0, 0))


class FormatTable(QWidget):
    """Two lists over one selection (`REQ-003`, `REQ-008`, `docs/UX_SPEC.md` §4 and §5).

    **One grid became two lists and the mode disappeared** (`T-310`, ruled 2026-09-09). The mode
    was what asked a user to declare *video + audio* before they had anything to declare it about,
    and it was what refused the two formats needing no merge at all. With the kinds in separate
    lists nothing has to be routed, so nothing is refused: taking a row from the video list fills
    the video half, taking one from the sound list fills the sound half, and taking a format that
    already carries both — or one the source never classified — is the whole download.

    **`FormatSelection` is unchanged and still holds the answer.** Its two modes remain; what
    changed is that they are now reached by *what was picked* rather than by a checkbox, so
    `choose` is only ever called on a format its mode can place and `UnplaceableFormatError` is
    unreachable from here.
    """

    #: `FormatInfo` — the current row named a format. **Reported, never acted on** (`P-14`).
    format_chosen = Signal(object)

    #: `FormatSelection` — what is chosen now, after any change (`T-108`).
    selection_changed = Signal(object)

    #: `str` — why the current selection cannot be committed, in the words the user should see.
    #: Reported rather than shown here (`UX-005` §5); today only ffmpeg's absence produces one.
    selection_refused = Signal(str)

    def __init__(
        self,
        formats: Sequence[FormatInfo] = (),
        parent: QWidget | None = None,
        *,
        ffmpeg_available: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("formatTable")
        self._ffmpeg_available = ffmpeg_available
        self._formats: tuple[FormatInfo, ...] = tuple(formats)
        #: The three things that can be picked, held apart and composed into a `FormatSelection`
        #: on demand. **Held apart because the mode is now derived** — see `_compose`.
        self._picked_video: FormatInfo | None = None
        self._picked_audio: FormatInfo | None = None
        self._picked_whole: FormatInfo | None = None
        self._selection = FormatSelection()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        lists = QHBoxLayout()

        self._video = FormatList(
            VIDEO_LIST_TITLE,
            video_formats(self._formats),
            VIDEO_LIST_COLUMNS,
            verb=self._video_verb,
            parent=self,
            group_key=sound_group,
        )
        self._video.chosen.connect(self.choose)
        lists.addWidget(self._video, VIDEO_LIST_SHARE)

        self._audio: FormatList | None = None
        self._no_audio: QLabel | None = None
        self._build_sound_list(lists)
        layout.addLayout(lists)

        # **`P-13`'s ffmpeg sentence, and it is *not* what suppresses a list** (`T-310`). The
        # ruling hid the merge *mode* when ffmpeg was absent; there is no mode now, and hiding the
        # sound list instead would be a worse answer than the one it replaced — an audio-only
        # format is a perfectly good download and needs no ffmpeg to fetch. So the lists stay, the
        # sentence is stated where somebody assembling a pair will read it, and `merge_refusal`
        # refuses the pair itself at commit (`REQ-024`).
        self._no_merge: QLabel | None = None
        if not ffmpeg_available and pairable(self._formats):
            stated = QLabel(NO_MERGE_WITHOUT_FFMPEG, self)
            stated.setObjectName("formatNoMerge")
            stated.setAccessibleName("Why merging is not offered")
            stated.setWordWrap(True)
            stated.setTextFormat(Qt.TextFormat.PlainText)
            self._no_merge = stated
            layout.addWidget(stated)

        # **What is chosen, in words** (`docs/UX_SPEC.md` §5, `NFR-005`). Unchanged by the split:
        # the spec asks for the pair to be *announced* rather than shown by highlight alone, so a
        # screen-reader user and a sighted user read the same sentence.
        self._chosen = QLabel(self)
        self._chosen.setObjectName("formatChosenLabel")
        self._chosen.setAccessibleName("Chosen formats")
        self._chosen.setWordWrap(True)
        layout.addWidget(self._chosen)

        for earlier, later in zip(self.focus_chain(), self.focus_chain()[1:], strict=False):
            QWidget.setTabOrder(earlier, later)
        self._announce()

    # Qt's override name, hence the camelCase.
    def sizeHint(self) -> QSize:
        """The width at which **every** list gets what it asked for (`T-310`).

        **A stretch factor makes the sum of the children's hints the wrong answer.** The lists sit
        in a `QHBoxLayout` with shares 3 and 2, so a child with share `s` of a total `S` receives
        `width * s / S` however much it asked for — and the widest list was still one pixel short
        at the width `QHBoxLayout` derived from the hints alone. So the requirement is inverted per
        child: for each, `width >= hint * S / s`, and the answer is the largest of those.

        This matters because `AddUrlDialog._widen_for` asks the panel how much room to make. A hint
        that is a pixel short is a horizontal scrollbar on a table that was resized precisely to fit
        — which is what the first three attempts at this produced, at 220px, 35px and finally 1px.
        """
        base = super().sizeHint()
        # **Whatever occupies the second slot, not only a sound list** (`T310-R2`). When a source
        # offers no audio half, `_build_sound_list` puts the explanation there **with the same
        # stretch** — so the row still divides 3:2 while this counted a total of 3 and handed the
        # video list every pixel it asked for. The video list then received three fifths of that
        # and scrolled sideways, on exactly the sources where the panel is simplest. The share is a
        # property of the slot, so the slot is what is asked.
        second: QWidget | None = self._audio if self._audio is not None else self._no_audio
        shares: list[tuple[QWidget, int]] = [(self._video, VIDEO_LIST_SHARE)]
        if second is not None:
            shares.append((second, AUDIO_LIST_SHARE))
        total = sum(share for _, share in shares)
        layout = self.layout()
        spacing = layout.spacing() * (len(shares) - 1) if layout is not None else 0
        needed = max(-(-panel.sizeHint().width() * total // share) for panel, share in shares)
        return QSize(max(base.width(), needed + spacing), base.height())

    def _build_sound_list(self, lists: QHBoxLayout) -> None:
        """The sound list, **or the reason there is none, in the same place** (`P-13`'s rule).

        **The condition is whether this source lists any audio-only stream — not whether a merge
        is possible.** Those are different questions and an earlier draft of this conflated them:
        it suppressed the list when `pairable` was false, which on a podcast — audio formats and
        no video ones — would have hidden every format the source offered. And it suppressed the
        list when ffmpeg was absent, which would have made an audio-only download impossible on a
        machine that needs no ffmpeg to perform one.

        **ffmpeg belongs to the pair, not to the list**, and `merge_refusal` already says so in
        `REQ-024`'s own words. It is asked on every change and reported through
        `selection_refused`, so the refusal arrives when a user has actually stated a merge.
        """
        audio = audio_formats(self._formats)
        if audio:
            self._audio = FormatList(
                AUDIO_LIST_TITLE,
                audio,
                AUDIO_LIST_COLUMNS,
                verb=self._audio_verb,
                parent=self,
            )
            self._audio.chosen.connect(self.choose)
            lists.addWidget(self._audio, AUDIO_LIST_SHARE)
            return

        stated = QLabel(NO_MERGE_WITHOUT_A_PAIR, self)
        stated.setObjectName("formatNoSoundList")
        stated.setAccessibleName("Why there is no sound list")
        stated.setWordWrap(True)
        stated.setAlignment(Qt.AlignmentFlag.AlignTop)
        # Plain text because the sentence can name what a source reported (`T016-R6`'s rule).
        stated.setTextFormat(Qt.TextFormat.PlainText)
        self._no_audio = stated
        lists.addWidget(stated, AUDIO_LIST_SHARE)

    # --- what the buttons say ------------------------------------------------------------

    def _video_verb(self, entry: FormatInfo) -> str:
        """**The button answers the row**, which is what makes one list hold two kinds of thing.

        *Use 22 — it has sound already* and *Use 614 for the video* are different actions, and a
        single fixed verb would have to be wrong for one of them.
        """
        kind = kind_of(entry)
        if kind is FormatKind.COMPLETE:
            return USE_COMPLETE.format(format_id=entry.format_id)
        if kind is FormatKind.UNKNOWN:
            return USE_UNCLASSIFIED.format(format_id=entry.format_id)
        return USE_VIDEO.format(format_id=entry.format_id)

    def _audio_verb(self, entry: FormatInfo) -> str:
        return USE_SOUND.format(format_id=entry.format_id)

    # --- the selection ---------------------------------------------------------------------

    def choose(self, entry: FormatInfo) -> None:
        """Take `entry` into the selection. **Nothing is refused** (`docs/UX_SPEC.md` §5).

        `P-2`'s routing is kept in full — a row goes to whichever slot its own kind matches — and
        the *mode* is derived by `_compose` from what has been picked rather than declared in
        advance. That is what makes the refusal unreachable.

        A format carrying both streams — or one nothing was said about — **replaces** the whole
        selection rather than joining it. It is the entire download, so a half left over from an
        earlier pick would be a second answer to a question already answered.
        """
        kind = kind_of(entry)
        if kind in (FormatKind.COMPLETE, FormatKind.UNKNOWN):
            self._picked_video = self._picked_audio = None
            self._picked_whole = entry
        elif kind is FormatKind.AUDIO_ONLY:
            self._picked_whole = None
            self._picked_audio = entry
        else:
            self._picked_whole = None
            self._picked_video = entry
        self._selection = self._compose()
        # **`selection_changed` before `format_chosen`, and the order is load-bearing** (`T-108`).
        # A listener on `format_chosen` may close the surface this table lives in; a listener on
        # `selection_changed` is what *writes the choice down*. Emitted the other way round,
        # closing tears the panel off its row first and the write finds nothing to write to.
        self._announce()
        self.format_chosen.emit(entry)

    def _compose(self) -> FormatSelection:
        """What has been picked, as a `FormatSelection`. **The mode is an outcome here.**

        **One half on its own is `SINGLE`, and getting that wrong was a real regression.** An
        earlier draft put every video-only pick into `PAIR`, where `is_complete` needs both slots
        filled — so choosing one video-only format and pressing *Done* named no download at all,
        and a silent-video download that `REQ-008` has always allowed became impossible. The mode
        is not a statement about the row's kind; it is a statement about how many things are
        being joined.

        `PAIR` therefore means exactly what `is_merge` reads it as: two streams the user has
        explicitly asked to be joined. `REQ-024`'s ffmpeg refusal rests on that, so widening
        `PAIR` to cover a half-filled selection would have made it fire on a download that needs
        no ffmpeg at all.
        """
        if self._picked_whole is not None:
            return FormatSelection(mode=SelectionMode.SINGLE, single=self._picked_whole)
        if self._picked_video is not None and self._picked_audio is not None:
            return FormatSelection(
                mode=SelectionMode.PAIR, video=self._picked_video, audio=self._picked_audio
            )
        lone = self._picked_video or self._picked_audio
        return FormatSelection(mode=SelectionMode.SINGLE, single=lone)

    def _announce(self) -> None:
        """Put the current selection where both a reader and a screen reader will find it."""
        described = self._selection.describe()
        picked = frozenset(entry.format_id for entry in self._selection.chosen())
        for panel in self.lists():
            panel.set_chosen(picked)
        self._chosen.setText(f"Chosen — {described}")
        self.setAccessibleDescription(f"{self._selection.mode}. Chosen: {described}")
        # **The sound list is never disabled** (`T310-R3`). It was, whenever a whole format was
        # chosen — on the reasoning that such a format leaves the sound list nothing to add. That
        # is true of what the sound list would *add* and false of what it can *replace*: `choose`
        # has always accepted an audio-only row as a new selection, clearing the whole one, and
        # disabling the control put a supported transition out of reach. The wording made it worse
        # on an unclassified entry, claiming *"that format has sound already"* about a format
        # nothing was said about.
        self.selection_changed.emit(self._selection)
        refusal = merge_refusal(self._selection, ffmpeg_available=self._ffmpeg_available)
        if refusal is not None:
            self.selection_refused.emit(refusal)

    # --- the seam a surface embedding this uses ------------------------------------------

    def lists(self) -> list[FormatList]:
        """Every list on this surface, in reading order. One or two, never none."""
        return [panel for panel in (self._video, self._audio) if panel is not None]

    def focus_chain(self) -> list[QWidget]:
        """The keyboard order, stated rather than left to construction order (`NFR-005`).

        Each list is body, then header, then its button — `docs/UX_SPEC.md` §4's body-then-header
        order, with the visible verb after the thing it acts on.
        """
        chain: list[QWidget] = []
        for panel in self.lists():
            chain.extend((panel.view, panel.header, panel.button))
        return chain

    @property
    def video(self) -> FormatList:
        return self._video

    @property
    def audio(self) -> FormatList | None:
        """The sound list, or `None` when the reason stands in its place."""
        return self._audio

    @property
    def no_sound_reason(self) -> QLabel | None:
        """Why there is no sound list, or `None` when there is one."""
        return self._no_audio

    @property
    def no_merge_reason(self) -> QLabel | None:
        """Why a pair cannot be merged here, or `None` when one can (`P-13`)."""
        return self._no_merge

    @property
    def table(self) -> QTableView:
        """The video list's view. **The surface's first focus**, and what `T-152` is about."""
        return self._video.view

    @property
    def model(self) -> FormatTableModel:
        return self._video.model

    @property
    def header(self) -> SortableHeader:
        return self._video.header

    def set_formats(self, formats: Sequence[FormatInfo]) -> None:
        """Replace what both lists show.

        **The sound list is not rebuilt**, so a source that had none still has none: whether it
        exists is decided once, at construction, from the formats the probe returned. A probe
        answers once (`FormatTableModel.set_formats`), so there is no second answer to take.
        """
        self._formats = tuple(formats)
        self._video.set_formats(video_formats(self._formats))
        if self._audio is not None:
            self._audio.set_formats(audio_formats(self._formats))
        # A selection naming formats this probe no longer offers is a claim about rows that are
        # gone. `T107-R4` made the *sort* survive a repopulation; what must not survive is a
        # choice of something no longer listed.
        self._picked_video = self._picked_audio = self._picked_whole = None
        self._selection = self._compose()
        self._announce()

    @property
    def selection(self) -> FormatSelection:
        """What is chosen now (`T-108`). The dialog reads this when it builds the request."""
        return self._selection

    def chosen_text(self) -> str:
        """The sentence the label and the accessible description both carry."""
        return self._chosen.text()

    def current_format(self) -> FormatInfo | None:
        """The current row of the list the keyboard is in, or of the video list."""
        for panel in self.lists():
            if panel.view.hasFocus():
                return panel.current_format()
        return self._video.current_format()

    def choose_current(self) -> None:
        """Take the current row of whichever list has focus (`REQ-008`)."""
        entry = self.current_format()
        if entry is not None:
            self.choose(entry)

    def sort_by(self, column: int) -> None:
        """Sort the video list. Each list owns its own sorting; this is the surface's default."""
        self._video.sort_by(column)
