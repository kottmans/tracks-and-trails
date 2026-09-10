"""Three ways to separate video from audio, with every format selectable (`T-310`).

**Two findings from the maintainer on 2026-09-09, and they have one cause.**

1. *"the video and audio codecs aren't clearly separated (all just in one big list)"*
2. *"the options with audio AND video aren't even selectable"*

Both come from putting three different kinds of thing in one grid. A shared grid forces shared
columns, so a video-only row has to say something in the audio-codec cell (`None`, softened to
`no sound` in `K`, and neither is information a person wanted) and an audio-only row has to say
something about resolution and fps. And a shared grid invites a **mode** to say which kind you
are picking — which is what refuses formats `22` and `18`, the two that already carry both
streams and need no merge at all (`ui/format_selection.py:194` raises on them).

**Separate the lists and both problems go away without a mode.**

- Each list carries only the columns its kind has. A video list needs no audio-codec column; an
  audio list needs no resolution and no fps. Every fact `REQ-003` names is still on screen, in
  the list where it means something — nine columns become six and four.
- Nothing is refused, because nothing has to be routed. Picking from the video list fills the
  video half; picking from the audio list fills the audio half; picking a complete format is the
  whole download and says so.

`P-14`'s *no filtering* is untouched: a filter is a control the user operates to hide rows, and
these are permanent, labelled, simultaneously visible lists. Nothing is ever hidden.

    .venv/bin/python tools/split_tables_mockup.py             # on the real display
    .venv/bin/python tools/split_tables_mockup.py --shots OUT # render each tab to a PNG
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.core.models import FormatInfo
from tracks_and_trails.ui import theme
from tracks_and_trails.ui.format_selection import FormatKind, kind_of
from tracks_and_trails.ui.format_table import UNKNOWN_TEXT, codec_name
from tracks_and_trails.ui.job_detail import format_bytes

#: A real YouTube probe's shape, trimmed to what fits a screenshot without scrolling.
#:
#: **Includes the awkward rows on purpose**: a progressive format that fills both slots at once,
#: an audio-only stream, and one whose bitrate yt-dlp never reported. An affordance that only
#: reads well on the tidy rows has not been looked at.
FORMATS = (
    FormatInfo(
        "614",
        "mp4",
        height=1080,
        width=1920,
        fps=24,
        bitrate_kbps=2124.0,
        video_codec="vp09.00.40.08",
        has_video=True,
        has_audio=False,
        filesize=41_500_000,
        note="1080p",
    ),
    FormatInfo(
        "399",
        "mp4",
        height=1080,
        width=1920,
        fps=24,
        bitrate_kbps=1710.0,
        video_codec="av01.0.08M.08",
        has_video=True,
        has_audio=False,
        filesize=33_400_000,
        filesize_is_estimate=True,
        note="1080p",
    ),
    FormatInfo(
        "137",
        "mp4",
        height=1080,
        width=1920,
        fps=24,
        bitrate_kbps=4114.0,
        video_codec="avc1.640028",
        has_video=True,
        has_audio=False,
        filesize=80_300_000,
        note="1080p",
    ),
    FormatInfo(
        "136",
        "mp4",
        height=720,
        width=1280,
        fps=24,
        bitrate_kbps=2192.0,
        video_codec="avc1.4d401f",
        has_video=True,
        has_audio=False,
        filesize=42_800_000,
        note="720p",
    ),
    FormatInfo(
        "22",
        "mp4",
        height=720,
        width=1280,
        fps=24,
        bitrate_kbps=1372.0,
        video_codec="avc1.64001F",
        audio_codec="mp4a.40.2",
        has_video=True,
        has_audio=True,
        filesize=26_800_000,
        note="720p",
    ),
    FormatInfo(
        "18",
        "mp4",
        height=360,
        width=640,
        fps=24,
        bitrate_kbps=613.0,
        video_codec="avc1.42001E",
        audio_codec="mp4a.40.2",
        has_video=True,
        has_audio=True,
        filesize=12_000_000,
        note="360p",
    ),
    FormatInfo(
        "140",
        "m4a",
        bitrate_kbps=129.0,
        audio_codec="mp4a.40.2",
        has_video=False,
        has_audio=True,
        filesize=2_500_000,
        note="medium",
    ),
    FormatInfo(
        "251",
        "webm",
        bitrate_kbps=141.0,
        audio_codec="opus",
        has_video=False,
        has_audio=True,
        filesize=2_700_000,
        note="medium",
    ),
    FormatInfo(
        "233", "mp4", audio_codec="mp4a.40.2", has_video=False, has_audio=True, note="Default, HLS"
    ),
)

SUMMARY = "Big Buck Bunny — youtube.com/watch?v=YE7VzlLtp-4"


def caption(text: str, parent: QWidget) -> QLabel:
    """The option's trade-off, on the screenshot rather than in a covering note."""
    label = QLabel(text, parent)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setContentsMargins(0, 0, 0, 8)
    return label


def heading(parent: QWidget) -> QLabel:
    """`RowPanel`'s summary line, so each tab is the panel and not a bare table."""
    label = QLabel(SUMMARY, parent)
    label.setTextFormat(Qt.TextFormat.PlainText)
    font = QFont(label.font())
    font.setBold(True)
    label.setFont(font)
    return label


def done_row(parent: QWidget, *, extra: QWidget | None = None) -> QHBoxLayout:
    """The panel's footer. `Done` is `RowPanel`'s, unchanged in every variant."""
    row = QHBoxLayout()
    if extra is not None:
        row.addWidget(extra)
    row.addStretch(1)
    close = QPushButton("&Done", parent)
    close.setAccessibleName("Use the chosen formats and close")
    row.addWidget(close)
    return row


CAPTION_N = (
    "<b>N — side by side.</b> Video on the left, sound on the right, both always visible, each "
    "with only the columns its kind has. Formats that already carry sound sit in the video list "
    "alongside their peers, with a <b>Sound</b> column reading <i>included</i> or <i>add one</i> — "
    "so at 720p the choice between 25.6 MB with sound and 40.8 MB without is one comparison in "
    "one place. Taking an <i>included</i> row greys the sound list and says why. <i>Costs:</i> "
    "two tables need width — measured at 1100px for the 10pt control, 100 more than "
    "<code>P</code>."
)
CAPTION_O = (
    "<b>O — stacked, three labelled sections.</b> <i>One file</i> first, because it is the "
    "simplest answer and needs no second pick; then video, then sound. Each is its own sortable "
    "table with its own columns. <i>Costs:</i> the tallest of the three, and the sound list can "
    "fall below the fold."
)
CAPTION_P = (
    "<b>P — side by side, with the ready-made ones on their own.</b> <code>N</code>'s two lists, "
    "but formats that already have both get a short list of their own rather than sitting in the "
    "video list. <i>Costs:</i> three regions instead of two, for a group that is often one or "
    "two rows — and the video list and the ready-made list can no longer be compared, which is "
    "the question this whole surface exists to answer."
)


def quality_of(entry: FormatInfo) -> str:
    return f"{entry.height}p" if entry.height else UNKNOWN_TEXT


def size_text(entry: FormatInfo) -> str:
    if entry.filesize is None:
        return UNKNOWN_TEXT
    return ("~" if entry.filesize_is_estimate else "") + format_bytes(entry.filesize)


def rate_text(entry: FormatInfo) -> str:
    return f"{entry.bitrate_kbps:.0f} kbps" if entry.bitrate_kbps else UNKNOWN_TEXT


def fps_text(entry: FormatInfo) -> str:
    if entry.fps is None:
        return UNKNOWN_TEXT
    return f"{entry.fps:g}"


@dataclass(frozen=True)
class Column:
    """One column of one list: what it is called, what it shows, and what it sorts on."""

    header: str
    show: Callable[[FormatInfo], str]
    key: Callable[[FormatInfo], object]


def codec_cell(codec: str | None) -> str:
    """`H.264`. Just the codec.

    **The plain-language gloss is gone, ruled by the maintainer on 2026-09-09**: *"anyone hand
    selecting the audio/video stream will hopefully know what they are doing"*. That is a
    statement about who this surface is for, and it is the right one — `docs/UX_SPEC.md` §4
    reaches this table through a row menu's *Choose specific formats…*, and the presets are the
    path for everyone else. Explaining `AV1` here was solving a problem the people who arrive
    here do not have.

    It also pays: the gloss was the widest thing on the row and forced the dialog to 1280px.

    `T-306`'s tool tip is untouched — the raw `avc1.640028` stays reachable, because `REQ-009`'s
    selector syntax and every bug report are written in it.
    """
    return codec_name(codec) if codec else UNKNOWN_TEXT


#: **Each list carries only the facts its kind has, in the order they are decided on.**
#:
#: Two rules, and the second one is the maintainer's 2026-09-09 finding that the attributes were
#: *"not in a sensible organizable way"*.
#:
#: 1. `REQ-003`'s eight fields are all present, but a video list does not ask a video what its
#:    audio codec is. That is what splitting the lists buys.
#: 2. **Left to right runs decision, then compatibility, then provenance.** `Quality` and `Size`
#:    are what a person compares two rows on, so they lead — and they lead in *every* list, so the
#:    eye has one left edge to read down rather than a different first column per section. Codec
#:    and its meaning follow, because they answer *will this play*. `Bitrate`, `File type` and
#:    `ID` are last: each is a fact `REQ-003` requires and none of them is why anyone clicks.
#:    `ID` is last of all, which is `T-306`'s ruling — it drew that column quieter than its row
#:    for the same reason — carried from emphasis into position.
VIDEO_COLUMNS: Final = (
    Column("Quality", quality_of, lambda e: e.height or -1),
    Column("FPS", fps_text, lambda e: e.fps or -1.0),
    Column("Size", size_text, lambda e: e.filesize if e.filesize is not None else -1),
    Column("Codec", lambda e: codec_cell(e.video_codec), lambda e: codec_name(e.video_codec or "")),
    Column("Bitrate", rate_text, lambda e: e.bitrate_kbps or -1.0),
    Column("File type", lambda e: e.extension, lambda e: e.extension),
    Column("ID", lambda e: e.format_id, lambda e: e.format_id),
)

AUDIO_COLUMNS: Final = (
    Column("Quality", rate_text, lambda e: e.bitrate_kbps or -1.0),
    Column("Size", size_text, lambda e: e.filesize if e.filesize is not None else -1),
    Column("Codec", lambda e: codec_cell(e.audio_codec), lambda e: codec_name(e.audio_codec or "")),
    Column("File type", lambda e: e.extension, lambda e: e.extension),
    Column("ID", lambda e: e.format_id, lambda e: e.format_id),
)

COMPLETE_COLUMNS: Final = (
    Column("Quality", quality_of, lambda e: e.height or -1),
    Column("FPS", fps_text, lambda e: e.fps or -1.0),
    Column("Size", size_text, lambda e: e.filesize if e.filesize is not None else -1),
    Column(
        "Picture", lambda e: codec_cell(e.video_codec), lambda e: codec_name(e.video_codec or "")
    ),
    Column(
        "Sound",
        lambda e: codec_name(e.audio_codec) if e.audio_codec else UNKNOWN_TEXT,
        lambda e: codec_name(e.audio_codec or ""),
    ),
    Column("Bitrate", rate_text, lambda e: e.bitrate_kbps or -1.0),
    Column("File type", lambda e: e.extension, lambda e: e.extension),
    Column("ID", lambda e: e.format_id, lambda e: e.format_id),
)

#: The video list as `N` uses it: **the same columns plus one saying whether sound is included.**
#:
#: **This exists because of a maintainer question that decided the layout** (2026-09-09): *"if
#: someone wants to individually select the video and audio track separately, why would they pick
#: one that had both below?"* They would not — which is what rules out `P`, where the two kinds
#: live in separate regions and cannot be compared. Mixing them into one list sorted by quality
#: puts the comparison that matters on screen: at 720p this source offers **25.6 MB with sound
#: included** or **40.8 MB video-only that still needs an audio track**. That is a real decision
#: and it is invisible in any layout that separates them.
#:
#: A column rather than a suffix on `Quality`, because it is a different fact from the resolution
#: and every row has an answer to it — *included* or *add one*.
VIDEO_MIXED_COLUMNS: Final = (
    VIDEO_COLUMNS[0],
    Column(
        "Sound",
        lambda e: (
            f"included · {codec_name(e.audio_codec or '')}"
            if kind_of(e) is FormatKind.COMPLETE
            else "add one"
        ),
        lambda e: kind_of(e) is FormatKind.COMPLETE,
    ),
    *VIDEO_COLUMNS[1:],
)


class SplitModel(QAbstractTableModel):
    """One kind's formats over one column set, sorting on the projection as `T-075` requires."""

    def __init__(self, formats, columns, parent=None, *, group_last=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(parent)
        self._formats = list(formats)
        self._columns = columns
        self._chosen: frozenset[str] = frozenset()
        #: A predicate whose matches sink to the bottom of every sort, or `None` for no grouping.
        self._group_last = group_last

    def format_at(self, row: int) -> FormatInfo | None:
        return self._formats[row] if 0 <= row < len(self._formats) else None

    def set_chosen(self, ids: frozenset[str]) -> None:
        self._chosen = ids
        if self._formats:
            self.dataChanged.emit(
                self.index(0, 0), self.index(len(self._formats) - 1, len(self._columns) - 1)
            )

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802, B008 - Qt override
        return 0 if parent.isValid() else len(self._formats)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802, B008 - Qt override
        return 0 if parent.isValid() else len(self._columns)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # type: ignore[no-untyped-def] # noqa: N802
        if orientation is Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self._columns[section].header
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):  # type: ignore[no-untyped-def]
        if not index.isValid():
            return None
        entry = self._formats[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return self._columns[index.column()].show(entry)
        if role == Qt.ItemDataRole.FontRole and entry.format_id in self._chosen:
            font = QFont()
            font.setBold(True)
            return font
        if role == Qt.ItemDataRole.ToolTipRole:
            codec = entry.video_codec or entry.audio_codec
            if not codec:
                return None
            return f"{codec} — {codec_name(codec)}"
        return None

    def sort(self, column, order=Qt.SortOrder.AscendingOrder) -> None:  # type: ignore[no-untyped-def]
        """Sort by `column`, then sink the grouped kind to the bottom.

        **Two passes rather than a compound key, and Python's stable sort is what makes it
        correct.** A single key of `(is_complete, column_key)` cannot express this: `reverse=True`
        would reverse the group flag too and float the complete formats to the top on any
        descending sort — which is the opposite of the ruling. Sorting by the column first and
        then by the group flag alone leaves the column's order intact inside each group.

        The grouping is the maintainer's 2026-09-09 call: *"list the video with attached audio
        last in the list together"*. It costs the adjacency argument — a 720p `included` row no
        longer sits beside the 720p `add one` row — but the two remain in one table with one set
        of columns, which is the comparison `P` cannot offer at all.
        """
        self.layoutAboutToBeChanged.emit()
        self._formats.sort(
            key=lambda entry: (self._columns[column].key(entry), entry.format_id),
            reverse=order is Qt.SortOrder.DescendingOrder,
        )
        if self._group_last is not None:
            self._formats.sort(key=self._group_last)
        self.layoutChanged.emit()


class KindPanel(QWidget):
    """One labelled list, its own sorting, and the one button that takes a row from it."""

    chosen = Signal(object)

    def __init__(self, title, formats, columns, verb, parent=None, *, group_last=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._title = QLabel(title, self)
        font = QFont(self._title.font())
        font.setBold(True)
        self._title.setFont(font)
        layout.addWidget(self._title)

        self.model = SplitModel(formats, columns, self, group_last=group_last)
        self.view = QTableView(self)
        self.view.setModel(self.model)
        self.view.setSortingEnabled(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.verticalHeader().setVisible(False)
        self.view.setTabKeyNavigation(False)
        self.view.setAccessibleName(title)
        # **Size to contents, and stretch nothing.** An earlier revision stretched the codec
        # column because it carried a sentence of plain English and was the one that degraded
        # gracefully when squeezed. The maintainer's 2026-09-09 ruling deleted that sentence, so
        # the widest cell on the row is now `included · AAC` — and the stretch that used to
        # rescue prose was instead inflating `H.264` to 415px. Every column now fits its content
        # and the table carries trailing space on the right, which is what the production table
        # already looks like.
        header = self.view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.view.activated.connect(lambda _index: self._take())
        layout.addWidget(self.view)

        self._verb = verb
        self.button = QPushButton(verb, self)
        self.button.clicked.connect(self._take)
        #: Given a row, the button's words. `None` keeps the fixed verb.
        #:
        #: **`N`'s video list holds two kinds of thing, so one fixed verb has to be wrong for
        #: one of them.** *Use this video* on format `22` understates it — that row is the whole
        #: download and needs nothing from the sound list. Saying so on the button is what makes
        #: `N` as unambiguous as `P`'s separate heading, without `P`'s third region.
        self.verb_for: object = None
        self.view.selectionModel().currentRowChanged.connect(lambda *_a: self._relabel())
        layout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignLeft)
        # **Opens on the column it leads with, best first.** `Quality` is column 0 in every list
        # by construction above, so this is one rule rather than one per section.
        self.view.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        if self.model.rowCount():
            self.view.setCurrentIndex(self.model.index(0, 0))
        self._relabel()

    def _relabel(self) -> None:
        entry = self.current()
        if self.verb_for is None or entry is None:
            self.button.setText(self._verb)
            return
        self.button.setText(self.verb_for(entry))

    def current(self) -> FormatInfo | None:
        index = self.view.currentIndex()
        return self.model.format_at(index.row()) if index.isValid() else None

    def _take(self) -> None:
        entry = self.current()
        if entry is not None:
            self.chosen.emit(entry)

    def set_dimmed(self, dimmed: bool, reason: str = "") -> None:
        """Greyed with a stated reason, never silently inert (`UX-005` §5)."""
        self.view.setEnabled(not dimmed)
        self.button.setEnabled(not dimmed)
        self.button.setText(reason if dimmed and reason else self._verb)


@dataclass
class Outcome:
    """What is chosen. **Nothing is ever refused** — that is the point of splitting the lists."""

    video: FormatInfo | None = None
    audio: FormatInfo | None = None
    whole: FormatInfo | None = None

    def take(self, entry: FormatInfo) -> Outcome:
        kind = kind_of(entry)
        if kind is FormatKind.COMPLETE:
            return Outcome(whole=entry)
        if kind is FormatKind.AUDIO_ONLY:
            return Outcome(video=self.video, audio=entry)
        return Outcome(video=entry, audio=self.audio)

    def ids(self) -> frozenset[str]:
        return frozenset(e.format_id for e in (self.video, self.audio, self.whole) if e is not None)

    def sentence(self) -> str:
        if self.whole is not None:
            return (
                f"<b>{quality_of(self.whole)} with sound</b> — one file, {size_text(self.whole)}. "
                f"Nothing to join."
            )
        if self.video is not None and self.audio is not None:
            total = (self.video.filesize or 0) + (self.audio.filesize or 0)
            return (
                f"<b>{quality_of(self.video)} {codec_name(self.video.video_codec or '')} "
                f"with {codec_name(self.audio.audio_codec or '')} sound</b> — "
                f"{format_bytes(total)}, joined into one file."
            )
        if self.video is not None:
            return (
                f"<b>{quality_of(self.video)}, no sound yet.</b> "
                f"Pick something from the sound list."
            )
        if self.audio is not None:
            return "<b>Sound only.</b> Pick something from the video list to add a picture."
        return "Nothing chosen yet."


def by_kind(kind: FormatKind) -> list[FormatInfo]:
    return [entry for entry in FORMATS if kind_of(entry) is kind]


class SplitVariant(QWidget):
    """Shared shell: the lists a subclass arranges, one result line, one `Done`."""

    caption_text = ""

    def arrange(self, layout: QVBoxLayout) -> None:
        raise NotImplementedError

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.outcome = Outcome()
        self.panels: list[KindPanel] = []
        layout = QVBoxLayout(self)
        layout.addWidget(caption(self.caption_text, self))
        layout.addWidget(heading(self))
        self.arrange(layout)
        for panel in self.panels:
            panel.chosen.connect(self._take)
        self.result = QLabel(self)
        self.result.setWordWrap(True)
        self.result.setFrameShape(QFrame.Shape.StyledPanel)
        self.result.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.result)
        layout.addLayout(done_row(self))
        self._sync()

    def make(self, title, kinds, columns, verb, *, group_last=None) -> KindPanel:  # type: ignore[no-untyped-def]
        formats: list[FormatInfo] = []
        for kind in kinds:
            formats.extend(by_kind(kind))
        panel = KindPanel(title, formats, columns, verb, self, group_last=group_last)
        self.panels.append(panel)
        return panel

    def _take(self, entry: FormatInfo) -> None:
        self.outcome = self.outcome.take(entry)
        self._sync()

    def _sync(self) -> None:
        ids = self.outcome.ids()
        for panel in self.panels:
            panel.model.set_chosen(ids)
        self.result.setText(self.outcome.sentence())
        self.after_sync()

    def after_sync(self) -> None:
        """A subclass that dims a list when a complete format is taken."""


class SideBySideVariant(SplitVariant):
    """`N` — two lists, complete formats living inside the video one."""

    caption_text = CAPTION_N

    def arrange(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()
        self.video = self.make(
            "Video",
            (FormatKind.VIDEO_ONLY, FormatKind.COMPLETE),
            VIDEO_MIXED_COLUMNS,
            "Use this video",
            group_last=lambda entry: kind_of(entry) is FormatKind.COMPLETE,
        )
        self.video.verb_for = lambda entry: (
            f"Use {entry.format_id} — it has sound already"
            if kind_of(entry) is FormatKind.COMPLETE
            else f"Use {entry.format_id} for the picture"
        )
        self.video._relabel()
        self.audio = self.make("Sound", (FormatKind.AUDIO_ONLY,), AUDIO_COLUMNS, "Use this sound")
        self.audio.verb_for = lambda entry: f"Use {entry.format_id} for the sound"
        # `verb_for` is assigned after `make()` has already labelled the button once, and `prime`
        # re-selects the row that is current anyway — so no signal fires. Relabel explicitly.
        self.audio._relabel()
        row.addWidget(self.video, 3)
        row.addWidget(self.audio, 2)
        layout.addLayout(row)

    def after_sync(self) -> None:
        complete = self.outcome.whole is not None
        self.audio.set_dimmed(complete, "That video already has sound")


class StackedVariant(SplitVariant):
    """`O` — three labelled sections, simplest answer first."""

    caption_text = CAPTION_O

    def arrange(self, layout: QVBoxLayout) -> None:
        self.complete = self.make(
            "One file — video and sound together",
            (FormatKind.COMPLETE,),
            COMPLETE_COLUMNS,
            "Use this — nothing else needed",
        )
        self.video = self.make("Video", (FormatKind.VIDEO_ONLY,), VIDEO_COLUMNS, "Use this video")
        self.audio = self.make("Sound", (FormatKind.AUDIO_ONLY,), AUDIO_COLUMNS, "Use this sound")
        layout.addWidget(self.complete)
        layout.addWidget(self.video)
        layout.addWidget(self.audio)


class ThreeRegionVariant(SplitVariant):
    """`P` — two lists side by side, ready-made ones on their own below."""

    caption_text = CAPTION_P

    def arrange(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()
        self.video = self.make("Video", (FormatKind.VIDEO_ONLY,), VIDEO_COLUMNS, "Use this video")
        self.audio = self.make("Sound", (FormatKind.AUDIO_ONLY,), AUDIO_COLUMNS, "Use this sound")
        self.audio.verb_for = lambda entry: f"Use {entry.format_id} for the sound"
        # `verb_for` is assigned after `make()` has already labelled the button once, and `prime`
        # re-selects the row that is current anyway — so no signal fires. Relabel explicitly.
        self.audio._relabel()
        row.addWidget(self.video, 3)
        row.addWidget(self.audio, 2)
        layout.addLayout(row)
        self.complete = self.make(
            "Or take one that already has both",
            (FormatKind.COMPLETE,),
            COMPLETE_COLUMNS,
            "Use this — nothing else needed",
        )
        layout.addWidget(self.complete)


VARIANTS = (
    ("N · Side by side", SideBySideVariant),
    ("O · Stacked sections", StackedVariant),
    ("P · Three regions", ThreeRegionVariant),
)


def prime(page: SplitVariant) -> None:
    """A video half taken and a sound row current — the state the pair is decided in."""
    video = getattr(page, "video", None)
    if video is not None:
        entry = video.model.format_at(0)
        if entry is not None and kind_of(entry) is not FormatKind.COMPLETE:
            page._take(entry)
    audio = getattr(page, "audio", None)
    if audio is not None and audio.model.rowCount():
        audio.view.setCurrentIndex(audio.model.index(0, 0))


def build(width: int = 1240) -> QTabWidget:
    tabs = QTabWidget()
    tabs.setWindowTitle("Video and sound, separated — three options")
    for label, factory in VARIANTS:
        page = factory()
        prime(page)
        tabs.addTab(page, label)
    tabs.resize(width, 760)
    return tabs


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shots", type=Path, help="render each tab to this directory and exit")
    parser.add_argument(
        "--width",
        type=int,
        default=1100,
        help="window width. Today's `AddUrlDialog` opens at 670px "
        "(`tools/dialog_width_floor_probe.py`), which is where side-by-side was found unusable. "
        "**1100 is measured, not chosen**: nothing truncates and no list scrolls sideways from "
        "1040px at this machine's 9pt font, 1100px at the 10pt positive control, 1220px at 11pt "
        "— so 1100 covers the control, the same reasoning the floor probe uses. It has been "
        "re-measured at every change rather than carried forward: 1160 before the `Sound` "
        "column, 1280 after it, and 1100 once the codec gloss was deleted. `P` needs 1000px, "
        "sixty less, because its lists are shorter. Pass 670 to see why widening is needed.",
    )
    parsed = parser.parse_args(argv)
    if parsed.shots is not None:
        import os

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication([])
    theme.apply(app, theme.THEMES["light"])
    tabs = build(parsed.width)
    tabs.show()
    if parsed.shots is None:
        return app.exec()

    parsed.shots.mkdir(parents=True, exist_ok=True)
    for position, (label, _factory) in enumerate(VARIANTS):
        tabs.setCurrentIndex(position)
        app.processEvents()
        page = tabs.widget(position)
        page.resize(tabs.width() - 16, tabs.height() - 40)
        app.processEvents()
        target = parsed.shots / f"{label[0].lower()}.png"
        page.grab().save(str(target))
        print(f"{target} {page.width()}x{page.height()}")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
