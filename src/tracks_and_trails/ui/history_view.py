"""What was obtained, after the queue has forgotten it (`T-100`, `REQ-020`, `REQ-021`).

## Why this exists at all

`P2PLAN-R8` found the history view had no owner in any phase: Phase 2's deliverables named the
records, Phase 3 is format depth, Phase 4 is settings, and `T-050` pointed at a "Phase 3"
deliverable that has never existed.

**Phase 2's own features combine into a hole without it.** `UX-001` says remove never deletes a
file; `T-081` delivers clear-completed. Together, in a Phase 2 with no history view, the user clears
their completed jobs, every file is still on disk, and **the application can no longer say where any
of it went**. That is this phase losing information the user needs, not a polish gap.

`REQ-021` — *open a completed file, or reveal it, from the **history and queue views*** —
presupposes this view and is a Phase 2 deliverable, which settles where it belongs.

## `HistoryEntry` is imported for typing only

`ARCHITECTURE.md` §3 has `ui/` depend on the *shape* of a repository rather than on `persistence`,
which is why `HistoryReader` is a protocol. The entry type is still needed to say what that protocol
returns, so it is imported under `TYPE_CHECKING`: the annotation is complete and **no runtime edge
from `ui/` to `persistence/` is created**. `app.py` supplies the concrete repository, as it does for
every other reader.

## It reports; it still writes nothing itself

This said *"Read-only, and deliberately so: nothing here removes a record"*, and that stopped being
true at `DAT-005` (2026-08-04), which admits removal of **selected records** and never a file.
`T-125` implements it, and the sentence is corrected here rather than left standing as a comment
that used to be right (`T124-R1` found the drawn `⋯` inert while this paragraph said removal did
not exist at all).

What is unchanged is where the write happens: this view **reports** a removal through
`removal_requested` and composition performs it, exactly as the queue reports its own verbs
(`ARCHITECTURE.md` §7). `T-086`'s open-and-reveal is reported the same way.

## No live signals, unlike the queue

`QueueModel` coalesces a stream of progress on a timer because a running job changes several times a
second. A history row is written once, by the completion transaction (`T050-R1`), and never changes
again — so this reads on construction and on an explicit `refresh()`, and has no timer, no
subscription and nothing to detach. Composition refreshes it when a job completes and when the queue
is cleared, which are the only two moments the set of rows can differ.

## A finished playlist is one row that opens

`T-145`, and `UX-005`'s 2026-08-05 amendment is where the rulings are. A sixteen-item playlist used
to land here as sixteen unrelated rows: the queue took trouble to show that they arrived together
and History dropped it at the point it became the only record of them.

**The flattening is `ui/grouping.py`'s, shared with `QueueModel`** — `UX-005` §3 makes both tabs one
row anatomy, and a second copy of the rules is how the two come to disagree. What stays here is
everything a *history* group says, which is not what a queue group says:

- **The chip is a count — `16 items`.** The 2026-08-04 amendment excluded History from the *state*
  chip because a `Done` on every row is noise; a count is not a state, so this is a different chip
  rather than a reversal of that ruling.
- **There is no segmented bar.** Every member succeeded by `DAT-005`'s definition of what reaches
  this list, so row 9b's bar would be sixteen identical blocks.
- **The count is of the members present — `14 items`, never `14 of 16`.** A denominator would
  describe two downloads History does not hold, and would be wrong about both numbers the moment a
  user removed one member.

**Membership is carried, never inferred.** Migration `0006` gives a record the three columns and the
completion transaction copies them from the job; a record written before that renders ungrouped, and
nothing tries to re-group it from titles or paths.
"""

from collections.abc import Sequence
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Any, Final, Protocol

from PySide6.QtCore import (
    QAbstractTableModel,
    QEvent,
    QItemSelectionModel,
    QModelIndex,
    QObject,
    QPoint,
    Qt,
    Signal,
)
from PySide6.QtCore import QPersistentModelIndex as _PersistentIndex
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListView,
    QVBoxLayout,
    QWidget,
)

from tracks_and_trails.ui.format_text import format_name
from tracks_and_trails.ui.grouping import Group, Visible, flatten
from tracks_and_trails.ui.job_detail import UNKNOWN_TEXT, format_bytes
from tracks_and_trails.ui.row_delegate import (
    DEPTH_ROLE,
    DETAIL_ROLE,
    EXPANDED_ROLE,
    HEADLINE_ROLE,
    HUE_ROLE,
    JOB_ID_ROLE,
    SELECTOR_ROLE,
    STATE_CHIP_ROLE,
    STATE_ROLE,
    THUMBNAIL_URL_ROLE,
    VERBS_ROLE,
    RowDelegate,
)
from tracks_and_trails.ui.row_verbs import Verb, history_group_verbs
from tracks_and_trails.ui.staging import placeholder_hue
from tracks_and_trails.ui.thumbnails import ThumbnailLoader, ThumbnailStore

if TYPE_CHECKING:
    from tracks_and_trails.persistence.repositories import HistoryEntry

#: The columns, in order. **Transcribed from `REQ-020` rather than generated from `HistoryEntry`'s
#: fields**, for the reason `COLUMN_HEADERS` gives one module over: the requirement names six things
#: a user must be able to see, and deriving the list from the dataclass would let a renamed or
#: dropped attribute quietly change what is on screen (`ai/TESTING.md` §13).
COLUMN_HEADERS: Final = ("Title", "Source URL", "Saved to", "Format", "Size", "Completed")

TITLE_COLUMN: Final = 0
URL_COLUMN: Final = 1
PATH_COLUMN: Final = 2
FORMAT_COLUMN: Final = 3
SIZE_COLUMN: Final = 4
COMPLETED_COLUMN: Final = 5

#: What an empty history says. A user who has downloaded nothing and a view that failed to load look
#: identical without it — the same reason the queue has one.
EMPTY_TEXT: Final = "Nothing downloaded yet. Completed downloads are listed here."

#: How the tooltip labels the value yt-dlp reported (`T-159`, `REQ-020`).
#:
#: Labelled rather than appended bare: a third line reading `399+140` under a URL and a path is
#: one more unexplained string, which is the defect this task is about rather than a fix for it.
RAW_FORMAT_PREFIX: Final = "Reported by yt-dlp: "

#: How a completion time is written. Seconds are dropped: this is a record of what happened, not a
#: measurement, and a column of times to the second is harder to scan for no gain.
COMPLETED_FORMAT: Final = "%Y-%m-%d %H:%M"

_ROOT: Final = QModelIndex()


class HistoryReader(Protocol):
    """The one read this view needs, named as a protocol (`ARCHITECTURE.md` §3).

    `ui/` depends on the shape of a repository rather than on `persistence`, exactly as `JobReader`
    and `QueueReader` do. `HistoryRepository` satisfies it; so does a list in a test.
    """

    def all_entries(self) -> list[HistoryEntry]: ...


def _text_or_absent(value: str | None) -> str:
    """A nullable string as itself, or `UNKNOWN_TEXT`.

    **`str(None)` reaching a cell is the defect this exists to prevent.** `title`, `output_path` and
    `format_used` are all nullable by design (`T-085`) — `format_used` specifically means "yt-dlp
    reported none", and printing `None` in a column headed *Format* tells the user a lie about a
    field that is honestly empty.
    """
    return value if value else UNKNOWN_TEXT


class HistoryModel(QAbstractTableModel):
    """Every completed download, newest first."""

    def __init__(self, *, history: HistoryReader, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._history = history
        self._entries: list[HistoryEntry] = []
        #: Which playlists are open. **Ids, not rows**, so it survives a refresh that reorders or
        #: removes: a group the user opened stays open when a new download lands above it.
        self._expanded: set[str] = set()
        self._visible: list[Visible[HistoryEntry]] = []
        self._visible_of: dict[str, int] = {}
        self.refresh()

    # --- the promises tests read -----------------------------------------------------------

    def download_count(self) -> int:
        """How many **downloads** History holds, which is not how many rows it shows (`T-145`).

        `QueueModel.download_count`'s ruling, one tab over: count the work, not the lines. A
        collapsed playlist of sixteen is one row and expanded it is seventeen, and neither is the
        answer to "how much is in here" — a tab count reading `rowCount()` would move when a user
        opened a group without History having changed.
        """
        return len(self._entries)

    def entry_ids(self) -> tuple[str, ...]:
        """Every record, in the durable order the repository gave them.

        **Not the visible rows, and the two diverge the moment a playlist is collapsed** — see
        `entry_id_at`, which is what a *row number* must be resolved through. This is the order
        History is written in, which is what `text_at` and the ordering criterion are about.
        """
        return tuple(entry.id for entry in self._entries)

    def entry_id_at(self, row: int) -> str | None:
        """The record a **visible row** is about, or `None` for a group header (`T-145`).

        `QueueModel.job_id_at`'s reasoning verbatim, and the defect it records is one this view
        would otherwise have acquired the day it grew groups: `entry_ids()` is every record, hidden
        or not, and the view's row numbers count only what is drawn. Indexing the first with the
        second resolves a visible row to a hidden member, and every file action then targets a
        record the user cannot see.

        `None` for a header rather than the group's id, because a caller asking "which record is
        this row" must not be handed a playlist id that never had a file.
        """
        if not 0 <= row < len(self._visible):
            return None
        entry = self._visible[row]
        if isinstance(entry, Group):
            return None
        return self._entries[entry].id

    def records_at(self, row: int) -> tuple[str, ...]:
        """Which records a visible row stands for: one, or a whole playlist (`T-145`).

        **This is where "removing a group removes its members" actually lives.** A header is not a
        record — it has no id in `history` and nothing to delete — so a removal that took row ids
        would either fail silently on the header or, worse, delete nothing while telling the user
        it had. Answering with the members means the existing selection-scoped route
        (`DAT-005` §1) removes a playlist correctly without a second removal path beside it, and
        the confirmation counts downloads rather than lines.

        Empty for a row this model does not have.
        """
        if not 0 <= row < len(self._visible):
            return ()
        entry = self._visible[row]
        if isinstance(entry, Group):
            return tuple(member.id for member in entry.members)
        return (self._entries[entry].id,)

    def reveal_target(self, row_id: str) -> str | None:
        """Which record's folder *Show in folder* should open for `row_id`, or `None` (`T142-R1`).

        **One place, asked by both the offer and the route.** For an ordinary row it is the record
        itself, when it names a file. For a group it is a member of the folder the group actually
        shares — and `None` the moment the members disagree, because then there is no folder that
        is the group's and choosing one would be choosing for the user.

        `None` is also the answer for a group whose records name no file at all, and for an id this
        model does not hold.
        """
        members = self.group_entries(row_id)
        if members:
            if self._common_folder(members) == UNKNOWN_TEXT:
                return None
            return next((member.id for member in members if member.output_path), None)
        return row_id if self.path_for(row_id) else None

    def records_for(self, row_id: str) -> tuple[str, ...]:
        """`records_at`, by id rather than by row — which records `row_id` stands for (`T-142`).

        A verb arrives naming the row it was drawn on, and that id is a *playlist* id for a header
        and a record id otherwise. The two spaces are not distinguishable by inspection, so this
        asks the visible groups — `QueueView._on_verb`'s authority, for the reason it records:
        routing on the verb alone is wrong, because `Show in folder` and `Remove` are offered by
        ordinary rows too.

        Empty for an id this model does not hold, so a verb routed against a group that was
        dissolved between the paint and the click acts on nothing.
        """
        members = self.group_entries(row_id)
        if members:
            return tuple(member.id for member in members)
        return (row_id,) if row_id in self.entry_ids() else ()

    def row_of(self, entry_id: str) -> int | None:
        """Where `entry_id` is drawn, or `None` when nothing shows it.

        A record inside a collapsed playlist has no line on screen, and `None` is the honest answer
        for it — building a `QModelIndex` from a hidden record selects whatever is at that number.
        """
        return self._visible_of.get(entry_id)

    def group_entries(self, playlist_id: str) -> list[HistoryEntry]:
        """Every record in `playlist_id`, in the playlist's own order, or empty for a non-group.

        **Empty rather than raising**, for `QueueModel.group_jobs`'s reason: the caller is acting on
        an id the view drew a moment ago, and a group dissolved between the paint and the click is
        an ordinary race rather than a programming error.
        """
        for entry in self._visible:
            if isinstance(entry, Group) and entry.group_id == playlist_id:
                return list(entry.members)
        return []

    def toggle_group(self, playlist_id: str) -> None:
        """Open or close a playlist. Called by the delegate's disclosure and by the arrow keys."""
        if playlist_id in self._expanded:
            self._expanded.discard(playlist_id)
        else:
            self._expanded.add(playlist_id)
        self.beginResetModel()
        self._rebuild_visible()
        self.endResetModel()

    def text_at(self, entry_id: str, column: int) -> str | None:
        """What one cell says, by entry rather than by row index.

        By id for `QueueModel.text_at`'s reason: a test that indexed by row would silently follow a
        reordering rather than noticing it, and the order is one of this view's own criteria.
        """
        for row, entry in enumerate(self._entries):
            if entry.id == entry_id:
                return self._text(self._entries[row], column)
        return None

    # --- Qt's model interface ---------------------------------------------------------------

    def rowCount(self, parent: QModelIndex | _PersistentIndex = _ROOT) -> int:
        """The **drawn** lines: headers, standalone records, and the members of open groups."""
        return 0 if parent.isValid() else len(self._visible)

    def columnCount(self, parent: QModelIndex | _PersistentIndex = _ROOT) -> int:
        """**One**, since `UX-005` (`T-124`).

        The six columns are gone from the *view* and survive as what the row says — `_text` and
        `COLUMN_HEADERS` are still the source of every string above, which is what keeps
        `REQ-020`'s fields named in one place. A list draws column 0, so the model offers one.
        """
        return 0 if parent.isValid() else 1

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole or orientation != Qt.Orientation.Horizontal:
            return None
        return COLUMN_HEADERS[section]

    def data(
        self,
        index: QModelIndex | _PersistentIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._visible):
            return None
        line = self._visible[index.row()]
        if isinstance(line, Group):
            return self._group_data(line, role)
        entry = self._entries[line]

        if role == DEPTH_ROLE:
            # **One level, and only for a member that is actually drawn under a header** (`T-140`).
            # A record whose playlist was dissolved to a single member is a top-level row and must
            # not be indented under a heading that is not there.
            return 1 if self._in_a_drawn_group(entry) else 0

        # **The delegate's roles, composed from the very cells `_text` answers** (`UX-005` §3,
        # `T-124`). History changes what the fields *say*, not what they are: where the queue row
        # shows progress and speed, this shows the saved path, the size and when. Each branch is
        # built from `_text` rather than from the record directly, so the row and a screen reader
        # cannot come to disagree — `QueueModel` states the same reasoning for the same reason.
        if role == HEADLINE_ROLE:
            return self._text(entry, TITLE_COLUMN)
        if role == DETAIL_ROLE:
            return " — ".join((self._text(entry, SIZE_COLUMN), self._text(entry, COMPLETED_COLUMN)))
        if role == STATE_ROLE:
            return self._text(entry, FORMAT_COLUMN)
        if role == SELECTOR_ROLE:
            # The saved path, on the row's own last line. `UX-005` §3 names it as one of the three
            # things history says, and it is the one a person copies into a bug report.
            return self._text(entry, PATH_COLUMN)
        if role == THUMBNAIL_URL_ROLE:
            # **History carries its own** (`T-138`, `UX-005` §3). It used to answer nothing, on
            # the recorded premise that "a history record carries no thumbnail URL" — true until
            # migration `0005` gave it one, and the reason the same download drew a picture in the
            # queue and a derived tile here the moment it finished.
            #
            # **From `entry`, never `self._entries[index.row()]`** (`T145-R2`). This method resolves
            # the visible row once, at the top; re-indexing the durable tuple with a row number is
            # the two-index-space defect one line deep. A closed two-member playlist compresses two
            # records into one line, so the ordinary row after it drew the *hidden* second member's
            # picture — and opening a group shifts every row after it, which can index past the
            # tuple entirely. The audit this task claims for `entry_id_at` and `verbs_of` missed it
            # because the expression reads like the line above it.
            return entry.thumbnail_url
        if role == HUE_ROLE:
            return placeholder_hue(entry.url)
        if role == JOB_ID_ROLE:
            return entry.id
        if role == VERBS_ROLE:
            # **Not `verbs_for`**, which answers for a `JobStatus`, and a history record has none:
            # it is not a job in a pipeline, it is what happened. `REQ-021` names the two things a
            # user does with a finished download and there is no third — removing one is `T-125`
            # and needs a `DAT-` decision before a button exists for it (`UX-005`).
            # `DAT-005` unblocked the third (2026-08-04). Before it, offering `Remove` would have
            # *been* the decision about what removal means — which is why `UX-005` §9 described the
            # control and refused to specify it.
            return (Verb.OPEN, Verb.REVEAL, Verb.REMOVE)

        if role == Qt.ItemDataRole.DisplayRole:
            return self._text(entry, index.column())
        if role == Qt.ItemDataRole.AccessibleTextRole:
            # **The whole row**, since `UX-005` made this a list (`T-124`). It used to name the
            # column — "Format: 137+140" — because a bare value out of six columns says nothing
            # about which field is being heard. There is one column now, and the equivalent of
            # naming the field is reading every field `REQ-020` names, in one sentence.
            # `QueueModel._whole_row` does the same thing for the same reason.
            return self._whole_row(entry)
        if role == Qt.ItemDataRole.ToolTipRole:
            # **The URL and the path in full**, which is what somebody copying either into a bug
            # report needs. They were per-column tooltips because both are routinely wider than
            # their column; on a row, the path is drawn on the last line and clipped when it is
            # long, so the need is unchanged and the tooltip is where it is met.
            #
            # **And the raw `format_used`, which is why this is where it went** (`T-159`). The row
            # now names the download in words, and `REQ-020` records *what happened* — an id is
            # what happened. Somebody debugging a download needs `399+140` and cannot get it from
            # the preset's name; somebody reading their history needs the name and would learn
            # nothing from the id. A tooltip is where the second reader is not charged for the
            # first one's question.
            return "\n".join(
                (
                    self._text(entry, URL_COLUMN),
                    self._text(entry, PATH_COLUMN),
                    f"{RAW_FORMAT_PREFIX}{_text_or_absent(entry.format_used)}",
                )
            )
        return None

    def _whole_row(self, entry: HistoryEntry) -> str:
        """Every field `REQ-020` names, in the order the row shows them.

        Built from `_text` and `COLUMN_HEADERS`, so the spoken row and the drawn row are two
        renderings of one set of cells rather than two descriptions that can drift.
        """
        return ", ".join(
            f"{COLUMN_HEADERS[column]}: {self._text(entry, column)}"
            for column in range(len(COLUMN_HEADERS))
        )

    def _text(self, entry: HistoryEntry, column: int) -> str:
        """One cell, from the record rather than from anything live.

        Ordered by column constant rather than by a lookup table, so a new column is a compile-time
        shaped change here and in `COLUMN_HEADERS` together.
        """
        if column == TITLE_COLUMN:
            return _text_or_absent(entry.title)
        if column == URL_COLUMN:
            # Never absent: `HistoryEntry.__post_init__` refuses a record without it, because
            # `REQ-020` names it and a retry cannot reconstruct it.
            return entry.url
        if column == PATH_COLUMN:
            return _text_or_absent(entry.output_path)
        if column == FORMAT_COLUMN:
            # **The words the rest of the window uses, not yt-dlp's id** (`T-159`, `T140-R3`).
            # `format_used` is what yt-dlp *reported* — `251` for YouTube's Opus stream, or
            # `399+140` for a merge, which is two ids joined by yt-dlp's own selector syntax. A
            # user reading their own history was told a number with no explanation available
            # anywhere in the window. `format_name` is the same rule the queue row and the add
            # dialog name a download by, reading the request migration `0007` carried across.
            #
            # **A record from before that migration still says what yt-dlp reported**, through
            # `_text_or_absent`'s existing rule: there is nothing to reconstruct a request from,
            # and an id labelled honestly is better than a name nobody wrote down. The raw value
            # stays reachable for every row either way — see the tooltip (`REQ-020`).
            if entry.format_choice is not None:
                return format_name(entry.format_choice)
            return _text_or_absent(entry.format_used)
        if column == SIZE_COLUMN:
            # The same function the queue and the detail view use, so one download is described
            # identically wherever it appears.
            return format_bytes(entry.bytes_total)
        if column == COMPLETED_COLUMN:
            return entry.completed_at.strftime(COMPLETED_FORMAT)
        return ""

    def _in_a_drawn_group(self, entry: HistoryEntry) -> bool:
        """Whether this record is a member of a playlist the list is actually drawing as a group."""
        return entry.playlist_id is not None and entry.playlist_id in self._visible_of

    def _group_size(self, group: Group[HistoryEntry]) -> str:
        """A playlist's total size, or `UNKNOWN_TEXT` when it is not knowable.

        **All or nothing, and the alternative is worse than it looks.** `bytes_total` is nullable —
        it means "the download reported none" — so summing the members that have one produces a
        number that is confidently too small, with nothing on the row to say so. A group of sixteen
        missing one entry's size would read as fifteen entries' worth and look exactly like a
        correct total. `UNKNOWN_TEXT` is what an ordinary row already shows for the same absence.
        """
        totals = [member.bytes_total for member in group.members]
        if any(total is None for total in totals):
            return UNKNOWN_TEXT
        return format_bytes(sum(total for total in totals if total is not None))

    def _common_folder(self, members: Sequence[HistoryEntry]) -> str:
        """The folder these records share, or `UNKNOWN_TEXT` when they do not.

        **Takes the members rather than a group**, because `T142-R1` made three callers of it: the
        header's folder line, the offer of *Show in folder*, and the route that performs it. All
        three must answer from one computation, which is what stopped the row contradicting itself.

        `UX-005` row 10 has a playlist's entries share one folder, which is what makes a single
        line meaningful here at all — but it is where they *were written*, and a user who changed
        the download folder mid-playlist has records that disagree. Disagreement is reported rather
        than papered over with the first member's answer, which is `T140-R3`'s rule for the queue
        header's format line.

        `PurePath` rather than `Path`: these are recorded strings and nothing here should touch a
        filesystem to render a row.

        **It reads them with the *running* platform's rules, which is an assumption worth naming.**
        `PurePath` is `PureWindowsPath` on Windows and `PurePosixPath` elsewhere, so a POSIX path
        read on Windows comes back reshaped with backslashes and a Windows path read on POSIX comes
        back as `.`. That is correct here because `DAT-001` puts the database under `platformdirs`,
        beside the machine that wrote the paths — the recorded shape and the reading platform always
        agree in production. A database carried to the other platform is the case it would not
        serve, and it is not one this project supports. Recorded because the Windows CI job proved
        the coupling exists rather than because it is currently wrong.
        """
        folders = {
            str(PurePath(member.output_path).parent) for member in members if member.output_path
        }
        return folders.pop() if len(folders) == 1 else UNKNOWN_TEXT

    def _group_data(self, group: Group[HistoryEntry], role: int) -> Any:
        """What a playlist's header row answers (`T-145`, `UX-005` amended 2026-08-05).

        The roles a *queue* header answers and this one does not are as much the decision as the
        ones it does: no `SEGMENTS_ROLE`, because every member succeeded and sixteen identical
        blocks is furniture; no `PRESET_CHOICES_ROLE`, because a record is not a download to
        retarget.
        """
        if role == HEADLINE_ROLE:
            return group.title
        if role == JOB_ID_ROLE:
            return group.group_id
        if role == EXPANDED_ROLE:
            return group.group_id in self._expanded
        if role == STATE_CHIP_ROLE:
            # **A count of the members present** — `14 items`, never `14 of 16`. History holds only
            # completed downloads, so a denominator counts rows it cannot describe; and records are
            # removable one at a time, so a stored original count would be wrong about both numbers
            # after the first removal.
            return f"{len(group.members)} items"
        if role == VERBS_ROLE:
            # **Derived from every member, not borrowed from the queue** (`T-142`). A history group
            # is terminal by definition, so `group_verbs()`'s `Cancel all` and `Retry failed` have
            # nothing to act on; what is left is `Show in folder` and a removal that names its
            # count. `history_group_verbs` is where that list is transcribed and why.
            #
            # **The offer is asked of the very function that draws the folder line** (`T142-R1`).
            # It was `any member has a path`, which offered *Show in folder* on a group whose own
            # line said it had no common folder — the row contradicting itself, and then routing to
            # whichever member came first.
            return history_group_verbs(
                has_one_common_folder=self._common_folder(group.members) != UNKNOWN_TEXT
            )
        if role == DETAIL_ROLE:
            # The same two facts an ordinary history row's second line carries, over the group.
            return " — ".join((self._group_size(group), self._group_completed(group)))
        if role == STATE_ROLE:
            # The one format its members share, or nothing when they do not. Where an ordinary row
            # says what it got, a header can only speak for the group when the group agrees.
            formats = {self._text(member, FORMAT_COLUMN) for member in group.members}
            return formats.pop() if len(formats) == 1 else ""
        if role == SELECTOR_ROLE:
            return self._common_folder(group.members)
        if role == THUMBNAIL_URL_ROLE:
            return next(
                (member.thumbnail_url for member in group.members if member.thumbnail_url), None
            )
        if role == HUE_ROLE:
            return placeholder_hue(group.members[0].url if group.members else group.title)
        if role in (Qt.ItemDataRole.AccessibleTextRole, Qt.ItemDataRole.DisplayRole):
            # **Spoken as a playlist, then every fact the header draws** (`T145-R3`, `NFR-005`).
            # `DisplayRole` answers the same text for `T-151`'s reason: `QListView` sizes its
            # content from it and the delegate draws something else, elided to the rect it is
            # given.
            #
            # **Composed from the same roles the header draws, not from a second list.** This said
            # only title, count, size and time — while the header visibly drew its common format
            # (`STATE_ROLE`) and its common folder (`SELECTOR_ROLE`), so a screen-reader user was
            # told less about the same downloads than a sighted one. That is `T017-R2`'s
            # two-vocabularies failure, and an ordinary History row already avoids it by building
            # `_whole_row` from the very cells it draws. Asking the roles is what keeps a fact
            # added to the header from having to be remembered here.
            spoken = [
                f"{group.title}. Playlist",
                f"{len(group.members)} items",
                self._group_size(group),
                f"completed {self._group_completed(group)}",
            ]
            # **Labelled from `COLUMN_HEADERS`**, as `_whole_row` labels an ordinary row's fields:
            # a bare path at the end of a sentence is a string a listener has to identify, and the
            # sighted reader has the row's layout to do that for them.
            #
            # Spoken **exactly when drawn**, which is what parity means. A group whose members
            # disagree about the format draws nothing for it, so nothing is said; one whose members
            # were written to different folders draws `UNKNOWN_TEXT`, which *is* on screen and so
            # is spoken.
            for column, drawn in (
                (FORMAT_COLUMN, self._group_data(group, STATE_ROLE)),
                (PATH_COLUMN, self._group_data(group, SELECTOR_ROLE)),
            ):
                if drawn:
                    spoken.append(f"{COLUMN_HEADERS[column]}: {drawn}")
            return ", ".join(spoken)
        return None

    def _group_completed(self, group: Group[HistoryEntry]) -> str:
        """When a playlist finished: its **most recent** member.

        Explicitly a maximum rather than the first member's time. The header sits where its newest
        member sits, because History is newest-first, but the members are ordered by
        `playlist_index` — so `members[0]` is track 01, which is very often the oldest of them.
        """
        latest = max(member.completed_at for member in group.members)
        return latest.strftime(COMPLETED_FORMAT)

    def ensure_visible(self, entry_id: str) -> int | None:
        """The row `entry_id` is drawn on, **opening its playlist if that is what it takes**.

        `select()` is how a named record is reached before a file verb acts on it (`T-086`), and a
        record inside a collapsed group has no row for that to land on. Silently failing would make
        *Open* do nothing for exactly the downloads a playlist contributed; selecting row `None`
        would act on whatever is at that number, which is worse.

        `None` only for a record this view does not hold at all.
        """
        row = self._visible_of.get(entry_id)
        if row is not None:
            return row
        for entry in self._entries:
            if entry.id != entry_id:
                continue
            # Reached only when the record is hidden, so its group is closed and this opens it —
            # `toggle_group` cannot close one here, because an open group's members have rows.
            playlist_id = entry.playlist_id
            if playlist_id is not None and playlist_id in self._visible_of:
                self.toggle_group(playlist_id)
                return self._visible_of.get(entry_id)
            return None
        return None

    def path_for(self, entry_id: str) -> str | None:
        """Where the file was written, or `None`. **Not `text_at(PATH_COLUMN)`** (`T-086`).

        That renders `UNKNOWN_TEXT` for a record with no path, which is right on screen and would
        be catastrophic as a filename — `open_file` would be handed the em-dash placeholder and
        refuse it for the wrong reason, reporting that a file named "—" is missing.
        """
        for entry in self._entries:
            if entry.id == entry_id:
                return entry.output_path
        return None

    def refresh(self) -> None:
        """Re-read every entry.

        A full reset rather than a diff: history changes when a download completes — rarely, and
        never in a burst — and there is no live state on a row to preserve across the rebuild, which
        is the one thing `QueueModel.refresh` has to be careful about.

        **The order is the repository's**, not this view's. `all_entries()` sorts by
        `completed_at DESC, id`; re-sorting here would be a second opinion about "newest" that could
        drift from the one the data has.
        """
        self.beginResetModel()
        self._entries = list(self._history.all_entries())
        self._rebuild_visible()
        self.endResetModel()

    def _rebuild_visible(self) -> None:
        """Flatten the records into headers and the rows not hidden (`T-145`).

        **The rules are `ui/grouping.flatten`'s**, shared with `QueueModel` so the two tabs cannot
        drift: the header at its first member's position, its members contiguous under it, a group
        of one dissolved.

        The two arguments that are History's own:

        - **`membership` reads the record, never the job.** The columns migration `0006` added are
          the record's own copy; a record written before it answers `None` and is drawn ungrouped.
        - **`order` is the playlist's index**, because this list is newest-completed-first and a
          playlist is not read in that order. Sixteen tracks that finished out of order still open
          as 01, 02, 03 — which is what `0006` carried `playlist_index` across for.
        """
        self._visible, self._visible_of = flatten(
            self._entries,
            membership=lambda entry: (
                None
                if entry.playlist_id is None
                else (entry.playlist_id, entry.playlist_title or entry.playlist_id)
            ),
            identity=lambda entry: entry.id,
            expanded=self._expanded,
            order=lambda entry: entry.playlist_index,
        )


class HistoryView(QWidget):
    """The table, plus the notice that stands in for it when there is nothing to show."""

    def __init__(
        self,
        *,
        history: HistoryReader,
        parent: QWidget | None = None,
        thumbnail_loader: ThumbnailLoader | None = None,
        cache_root: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("historyView")
        self._model = HistoryModel(history=history, parent=self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._empty = QLabel(EMPTY_TEXT, self)
        self._empty.setObjectName("historyEmptyNotice")
        self._empty.setAccessibleName("History is empty")
        self._empty.setTextFormat(Qt.TextFormat.PlainText)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty)

        # **A list behind `RowDelegate`, not a six-column table** (`UX-005` §3, `T-124`). The
        # columns were `T-100`'s and they were right for a table; `UX-005` makes both tabs the
        # same row anatomy, so a user reads one shape rather than two. The fields `REQ-020` names
        # all survive — `_text` still produces every one of them — as *what the row says*.
        self._table = QListView(self)
        self._table.setObjectName("historyTable")
        # **As wide as the viewport, never wider** (`T-151`). See `queue_view` for the mechanism:
        # `QListView` sizes its content from `DisplayRole`, this model answers that with the whole
        # row's text, and the delegate draws something else elided to the rect it is given. History
        # draws the same anatomy through the same delegate, so it had the same defect.
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._table.setResizeMode(QListView.ResizeMode.Adjust)
        self._table.setAccessibleName("Download history")
        self._table.setAccessibleDescription(
            "Completed downloads, most recent first. Files are not removed from disk by anything "
            "in this list."
        )
        self._table.setModel(self._model)
        # **Extended, since `DAT-005`**: removal is selection-scoped and its verb names its own
        # count, and a count is decoration if only one row can ever be selected.
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        # Read-only, and not merely unedited: `REQ-020` is a record of what happened, and an
        # editable view would also put a text cursor into the keyboard order.
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setUniformItemSizes(True)
        # **The overflow's keyboard route** (`UX-005` §4, `T124-R1`). Qt raises
        # `customContextMenuRequested` for the Menu key and Shift+F10 as well as for the mouse, so
        # one connection makes `⋯` reachable both ways. `FileActions` is told not to install its
        # own menu on this table, because two menus on one gesture is worse than either.
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._row_menu_asked_for)
        # **A store of its own** (`T-138`). This said "no thumbnail store: a history record
        # carries no thumbnail URL", which migration `0005` made false — and until it did, the
        # same download drew its picture in the queue and a derived tile here, one row apart.
        #
        # Its own rather than the queue's: the two views are built independently and neither owns
        # the other, and the **disk** cache is shared anyway — `thumbnail_cache_path` keys by URL,
        # so a picture fetched for a queue row is already on disk when History asks for it. What
        # is duplicated is an in-memory cache and a thread pool, which is what `T-119` sized per
        # view.
        self._thumbnails = ThumbnailStore(
            loader=thumbnail_loader, cache_root=cache_root, parent=self
        )
        self._delegate = RowDelegate(thumbnails=self._thumbnails, parent=self._table)
        self._table.setItemDelegate(self._delegate)
        self._thumbnails.ready.connect(self._on_thumbnail_ready)
        # **The pointer is watched so the row's verbs can react to it** (`T-134`). Not a
        # default: a viewport's mouse tracking is off, so without this Qt reports the
        # pointer only while a button is held.
        self._delegate.watch_hover(self._table)
        self._delegate.verb_triggered.connect(self._on_verb)
        # **A playlist opens and closes here too** (`T-145`, `UX-005` §3). The same delegate draws
        # the same disclosure on both tabs, so the same two routes have to exist on both: the
        # triangle, and the arrow keys below. A group that only a pointer can open is the defect
        # `T140-R5` fixed one tab over.
        self._delegate.disclosure_toggled.connect(self._model.toggle_group)
        self._table.installEventFilter(self)
        layout.addWidget(self._table)

        # **The paint-time overflow record does not survive a reset** (`T-135`). A job that
        # left the queue would otherwise keep an entry keyed by its id, and rows that
        # scroll out of view are never repainted to correct it.
        self._model.modelReset.connect(self._delegate.forget_dropped)
        self._model.modelReset.connect(self._show_the_right_thing)
        # **The same keyboard route, so the same hole to fill** (`T-152`). History declares the
        # `⋯` route too, and a view with no current index answers it with nothing.
        self._model.modelReset.connect(self._ensure_a_current_row)
        self._show_the_right_thing()
        self._ensure_a_current_row()

    #: `(entry_id)` — a row's file verb was activated. Reported rather than performed, because
    #: `FileActions` owns containment (`SEC-001`) and the shell owns `FileActions`.
    open_requested = Signal(str)
    reveal_requested = Signal(str)

    #: `(entry_ids)` — the user asked to remove what they selected (`DAT-005`, `UX-005` §9).
    #: **The whole selection**, not the row the verb was drawn on: `DAT-005` scopes removal to the
    #: selection and makes the verb name its own count, so sending one id would make the count a
    #: decoration.
    removal_requested = Signal(list)

    #: `(entry_id)` — the row's `⋯` was activated, by pointer or by keyboard (`T124-R1`).
    #: The queue's signal of the same name, for the same reason: what belongs in the overflow is a
    #: shell question, and the shell builds one menu for both tabs.
    #: A row asked for its menu: the row's id, and **what the menu should hold** (`T-135`).
    #:
    #: The contents travel with the request because the two routes want different things and only
    #: this widget can tell them apart. The `⋯` button holds what the row could not draw — that is
    #: what it is for, and listing everything there offered the same actions twice on any row wide
    #: enough to show them. The Menu key, Shift+F10 and a right-click hold **everything the state
    #: permits**, because they are not asking about the row's width.
    more_requested = Signal(str, object)

    def _on_verb(self, entry_id: str, verb: object) -> None:
        """Route a history row's verb, or its overflow. An unrouted verb is a programming error.

        Three verbs and the `⋯`, which the delegate reports as `None`. *(This said "only two
        exist" — written when it was true, and still there after `DAT-005` added *Remove*, in the
        method whose missing `None` branch made the `⋯` inert.)*
        """
        if verb is None:
            # **The drawn `⋯` did nothing at all until `T124-R1`.** The delegate emits `None` for
            # the overflow and this method's final branch tested `verb is not None`, so the one
            # control every history row draws was inert — with a pointer as well as without one.
            # `QueueView._on_verb` had the branch; this is the same route, added where it was
            # missing rather than a second one beside it.
            self.more_requested.emit(entry_id, self._delegate.overflowing(entry_id))
            return
        # **What this row stands for, resolved once** (`T-142`). For a group header that is its
        # members; for an ordinary row it is the one record. Both verbs below act on records, so
        # neither has to know which kind of row reported it — and a header id, which names nothing
        # in `history`, never escapes this method.
        own = self._model.records_for(entry_id)
        if not own:
            return
        if verb is Verb.OPEN:
            # **A header is refused rather than resolved.** A group does not offer this — there is
            # no one file to open, and picking one would be a decision rather than an
            # implementation — so this acts only when the row *is* the record.
            if own == (entry_id,):
                self.open_requested.emit(entry_id)
        elif verb is Verb.REVEAL:
            # **Re-checked here, not trusted from the offer** (`T140-R6`, `T142-R1`). The verb the
            # row drew came from the model a moment ago; what has to hold at routing time is that
            # the records still name **one** folder. For a group that is `reveal_target`, which
            # answers `None` the moment the members disagree — so a header drawn before a record
            # was removed, and clicked after, cannot reveal a folder that is no longer the group's.
            target = self._model.reveal_target(entry_id)
            if target is not None:
                self.reveal_requested.emit(target)
        elif verb is Verb.REMOVE:
            # **The selection, and what was clicked if it is not in it.** A user who clicks Remove
            # on an unselected row means that row; one who has three selected and clicks Remove on
            # one of them means the three (`DAT-005` §1). A header is "in" the selection when every
            # record it stands for is, which is the same rule read one level up.
            selected = self.selected_entry_ids()
            covered = all(each in selected for each in own)
            self.removal_requested.emit(list(selected) if covered else list(own))
        else:
            raise AssertionError(f"a history row offered {verb!r} and nothing routes it")

    def trigger_verb(self, entry_id: str, verb: Verb) -> None:
        """Activate a verb from the overflow or a key, by the route a click takes."""
        self._on_verb(entry_id, verb)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """`Right` opens the focused playlist and `Left` closes it (`T-145`, `NFR-005`).

        `QueueView.eventFilter` is the same filter for the same reasons, and both are one sentence:
        `EXPANDED_ROLE` answers `None` for an ordinary row, so a record that is not a header sees
        these keys exactly as it did before, and the two keys are directional rather than a toggle
        because `Right` on an open group should leave it open.
        """
        if watched is self._table and event.type() == QEvent.Type.KeyPress:
            key = event.key()  # type: ignore[attr-defined]
            if key in (Qt.Key.Key_Right, Qt.Key.Key_Left):
                index = self._table.currentIndex()
                expanded = self._model.data(index, EXPANDED_ROLE)
                playlist_id = self._model.data(index, JOB_ID_ROLE)
                if isinstance(expanded, bool) and isinstance(playlist_id, str) and playlist_id:
                    wants_open = key == Qt.Key.Key_Right
                    if wants_open != expanded:
                        self._model.toggle_group(playlist_id)
                    # Consumed either way: `Right` on an open group is a no-op the user asked for.
                    return True
        return bool(super().eventFilter(watched, event))

    def verbs_of(self, entry_id: str) -> tuple[Verb, ...]:
        """What the row for `entry_id` offers, asked of the model the delegate asks (`T124-R1`).

        **Read through the role rather than recomputed**, for `QueueView.verbs_of`'s reason: the
        overflow exists to hold what the row could not fit, so a menu that disagreed with the row
        would be worse than no menu.

        **Resolved through `row_of`, not through `entry_ids()`** (`T-145`). Those were the same
        number until History grew groups and are not now: `entry_ids()` counts every record and a
        row number counts only what is drawn, so indexing one with the other read the verbs of a
        different row the moment a playlist was collapsed above it. Empty for anything this view is
        not drawing — including a record hidden inside a closed group, which has no row to offer
        verbs on.
        """
        row = self._model.row_of(entry_id)
        if row is None:
            return ()
        offered = self._model.data(self._model.index(row, 0), VERBS_ROLE)
        return tuple(offered or ())

    def _on_thumbnail_ready(self, _url: str) -> None:
        """A picture arrived, so the rows showing it repaint (`T-138`).

        The same shape as `QueueView._on_thumbnail_ready`: the *history* did not change, so this
        repaints rather than refreshing — a reset here would discard the selection a user made
        while a picture was still loading.
        """
        count = self._model.rowCount()
        if count:
            self._model.dataChanged.emit(self._model.index(0, 0), self._model.index(count - 1, 0))

    def _row_menu_asked_for(self, position: QPoint) -> None:
        """The Menu key, Shift+F10 or a right-click asked for a row's overflow (`T124-R1`).

        `QueueView._row_menu_asked_for` is the same method for the same reason, including the
        fall back to the current row when the position names none — which is the keyboard case,
        and which is what makes **history removal keyboard-reachable at all**. Before this the
        only route to *Remove* was a pointer on a control that did nothing.
        """
        at = self._table.indexAt(position)
        index = at if at.isValid() else self._table.currentIndex()
        if not index.isValid():
            return
        entry_id = self._model.data(index, JOB_ID_ROLE)
        if isinstance(entry_id, str) and entry_id:
            # Everything: see `QueueView`'s twin. A keyboard route must not depend on the width.
            self.more_requested.emit(entry_id, self.verbs_of(entry_id))

    @property
    def model(self) -> HistoryModel:
        return self._model

    @property
    def table(self) -> QListView:
        return self._table

    @property
    def shows_empty_notice(self) -> bool:
        return not self._empty.isHidden()

    def empty_text(self) -> str:
        return self._empty.text()

    def refresh(self) -> None:
        self._model.refresh()

    def selected_entry_id(self) -> str | None:
        """Which record is selected, or `None`. **`T-086` is what this exists for.**

        `selectedIndexes` rather than `selectedRows`: a `QListView` has one column, and
        `selectedRows` is a table-shaped question that returns nothing here.
        """
        indexes = self._table.selectionModel().selectedIndexes()
        if not indexes:
            return None
        # `entry_id_at`, never `entry_ids()[row]` (`T-145`): a row number counts drawn lines and
        # `entry_ids()` counts records. `None` for a group header, which has no file to act on.
        return self._model.entry_id_at(indexes[0].row())

    def selected_entry_ids(self) -> tuple[str, ...]:
        """Every selected record, in the order the list shows them.

        `DAT-005` §1 scopes removal to the selection, so this is what the verb acts on and what
        its count counts. Ordered by row rather than by click, because a confirmation naming three
        downloads should list them the way they are on screen.

        **A selected group header contributes its members** (`T-145`). A header is not a record and
        has no id of its own to remove; what a user selecting the line for a sixteen-item playlist
        has selected is the sixteen. That is also what makes the confirmation say *these 16* rather
        than counting a line — and what keeps `DAT-005` §4's count honest now that one line can
        stand for many records.

        Deduplicated, because selecting a header *and* one of its open members is one gesture a
        user can make and two paths to the same id — and a count that said 17 for sixteen downloads
        would be exactly the decoration `DAT-005` §4 forbids.
        """
        chosen: list[str] = []
        seen: set[str] = set()
        for row in sorted(index.row() for index in self._table.selectionModel().selectedIndexes()):
            for entry_id in self._model.records_at(row):
                if entry_id not in seen:
                    seen.add(entry_id)
                    chosen.append(entry_id)
        return tuple(chosen)

    def select(self, entry_id: str) -> bool:
        """Select the row for `entry_id`, so a named verb can act through the selection.

        Opens the record's playlist when it is closed (`ensure_visible`), because otherwise *Open*
        and *Show in folder* would silently do nothing for any download that arrived in one.
        """
        row = self._model.ensure_visible(entry_id)
        if row is None:
            return False
        self._table.setCurrentIndex(self._model.index(row, 0))
        return True

    def selected_path(self) -> str | None:
        """The selected record's file, or `None`. **`T-086`'s one question of this view.**"""
        entry_id = self.selected_entry_id()
        return None if entry_id is None else self._model.path_for(entry_id)

    def focus_chain(self) -> list[QWidget]:
        """The keyboard order, per state (`NFR-005`, `T-060`'s rule).

        The table is not in the chain when it is hidden: naming a widget the user cannot see is
        exactly what `T-060` found the queue doing.
        """
        return [self._table] if self._model.rowCount() else []

    def _ensure_a_current_row(self) -> None:
        """Point the table at its first row when nothing is current (`T-152`, `NFR-005`).

        Current, not selected — the keyboard's position rather than a statement about what the user
        chose. Fills a hole only, so a refresh cannot move the keyboard out from under someone.
        """
        if self._model.rowCount() and not self._table.currentIndex().isValid():
            # **`NoUpdate`, so this is current and not selected.** `setCurrentIndex` on
            # the view selects as well, which would offer the per-row file actions for a
            # row nobody chose — `T-086`'s rule is that they follow a *selection*.
            self._table.selectionModel().setCurrentIndex(
                self._model.index(0, TITLE_COLUMN), QItemSelectionModel.SelectionFlag.NoUpdate
            )

    def _show_the_right_thing(self) -> None:
        """The table when there are rows, the notice when there are none. Never both."""
        has_rows = self._model.rowCount() > 0
        self._table.setVisible(has_rows)
        self._empty.setVisible(not has_rows)


def build_history_view(
    history: HistoryReader,
    *,
    thumbnail_loader: ThumbnailLoader | None = None,
    cache_root: Path | None = None,
) -> HistoryView:
    """Construct the view. A named function for `build_queue_view`'s reason.

    There is nothing to wire yet — `T-086` adds open-and-reveal, and this is where that wiring
    decision will live rather than being buried in composition.
    """
    return HistoryView(history=history, thumbnail_loader=thumbnail_loader, cache_root=cache_root)
