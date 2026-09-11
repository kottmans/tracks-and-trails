"""One drawn row, for both the staging list and the queue (`T-118`, `T-119`, `REQ-002`).

Two surfaces show the same thing — a thumbnail, what the item is, and where it has got to — and
before this they drew it twice. The add dialog put a `QWidget` on every row; the queue laid out a
grid of six text columns. This module draws it once, and that single fact is what closes three
findings at the same time rather than one at a time:

- **`T118-R7`** — the row widget collided with the item delegate, so a 54 px thumbnail was clipped
  into a 25 px row. There is no row widget now, and `ROW_HEIGHT` is derived from the thumbnail it
  has to contain rather than left to whatever the default metrics produce.
- **`T118-R9`** — the per-row controls sat outside the declared focus order and landed after
  *Close*. An editor a delegate opens belongs to the row, is reached through the row, and cannot
  land anywhere in the tab order because it is not in it: `EDIT_KEY` is the declared route, and it
  is stated here rather than inherited from a Qt default nobody wrote down.
- **`T118-R10`** — a paste of 150 cost 0.722 s on hosted Windows because it built 150 widgets. A
  delegate builds **one editor, for the row being edited**, and paints the rest. What used to grow
  with the paste is now flat in it.

## Roles, not columns

The delegate reads its row through named roles rather than through column indices, so the two
models feeding it need not agree on a column layout — the staging list has one column of rows, the
queue has one column of jobs, and each answers the same questions. A role a model does not answer
is simply absent from the drawing; nothing is required except `HEADLINE_ROLE`.

**Every field is text, and every state is a word** (`NFR-005`). The painted progress bar is
decoration over `DETAIL_ROLE`, which already says the same thing in words — this is the rule that
colour never carries meaning alone, applied to the one graphical element here. It is also not a
`QProgressBar`: `queue_view.py` rejected a widget per row and that reasoning is untouched, because
a painted rectangle is not a widget and costs nothing per row.
"""

from collections.abc import Sequence
from enum import StrEnum
from typing import Any, Final, cast

from PySide6.QtCore import (
    QAbstractItemModel,
    QEvent,
    QModelIndex,
    QPoint,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtCore import QPersistentModelIndex as _PersistentIndex
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPalette,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemDelegate,
    QAbstractItemView,
    QApplication,
    QComboBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionButton,
    QStyleOptionComboBox,
    QStyleOptionViewItem,
    QWidget,
)

from tracks_and_trails.core.models import MediaKind
from tracks_and_trails.ui import theme
from tracks_and_trails.ui.row_verbs import LABELS, MORE_LABEL, Verb
from tracks_and_trails.ui.thumbnails import THUMBNAIL_SIZE, ThumbnailStore


class SegmentState(StrEnum):
    """What one block of a group's segmented bar says about its entry (`T-140`).

    **Words, not colours** (`NFR-005`). The bar is drawn from these and so is the group's
    accessible text, so the thing a sighted user sees and the thing a screen reader is told come
    from one source rather than two that can drift.
    """

    DONE = "done"
    RUNNING = "running"
    FAILED = "failed"
    #: **Not a kind of failure** (`T-165`). Both were one state, and because this enum is the
    #: single source for the drawing *and* the words, the collapse showed twice: a playlist the
    #: user cancelled reported itself as `16 failed`, sending somebody to look for an error that
    #: does not exist. Separating them here separates both surfaces at once, which is the whole
    #: reason the enum is shared rather than duplicated.
    CANCELLED = "cancelled"
    WAITING = "waiting"


#: The headline: a title once something has read one, else the URL the user pasted. Never empty —
#: a row nobody can identify is worse than a long URL.
HEADLINE_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 1

#: The second line: uploader, duration and kind for a staged row; size, speed and ETA for a
#: running one. In words, always.
DETAIL_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 2

#: **What the user can do about this row's failure** — the third of `NFR-006`'s three facts
#: (`T-201`, `T201-R3`, `UX-005` ruled 2026-08-14).
#:
#: `NFR-006` asks for *what failed, why, and what the user can do*. The row already carried the
#: first two: `HEADLINE_ROLE` names the job, and `DETAIL_ROLE` carries the class in plain words
#: followed by the extractor's own message. The third had a written, tested text and **no reachable
#: surface** — `describe_failure` composed it only for `JobProgressView`, which `UX-005` §2's
#: removal of the detail pane left nothing constructing. So a user was told what failed and never
#: told what to do, which is the requirement's own third clause missing from the product.
#:
#: **Its own line, and its own role, because the alternatives were measured and refused.** Putting
#: it as a third clause on `DETAIL_ROLE`'s line elided the extractor's `--ffmpeg-location` to
#: `--ff…` at 1180 px — cutting the words `NFR-006` protects hardest — and putting it in place of
#: the format line would overturn `UX-005` §6's plain-format-text-after-start for one row state.
#: The maintainer ruled the extra line on 2026-08-14; `sizeHint` and `_paint_text` both derive it
#: from this role, so the height and the drawing cannot disagree about whether it is there.
#:
#: **Empty is the ordinary answer.** Every row that has not failed answers `""`, and so does a
#: failure with no honest action — `GEO_RESTRICTED`, `DRM_PROTECTED` — which keeps the row at the
#: anatomy `UX-005` §3 states and spends the height only where there is something to say. That is
#: the same conditional-height rule a playlist entry's format line already follows.
ACTION_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 24

#: Where the row has got to, in words (`NFR-005`): "Reading", "Downloading video", "Couldn't read".
STATE_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 3

#: The picture to draw, as a URL. The delegate asks the store for it while painting and never
#: fetches anything itself — see `thumbnails.ThumbnailStore.pixmap`.
THUMBNAIL_URL_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 4

#: The hue of the derived tile drawn until a picture arrives (`staging.placeholder_hue`).
HUE_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 5

#: What this row will be downloaded **as** — a `MediaKind`, or `None` where nothing single is true
#: (`T-217`).
#:
#: Only the placeholder tile reads it, to mark the absence of artwork as *audio* or *video* rather
#: than as a bare colour block. **Asked of the model rather than derived here**, on the rule
#: `STATE_CHIP_ROLE` and `T-186` set: a model that never sets it gets the unmarked tile without the
#: role exists — which is what keeps the two other models in this tree, and any test model, working
#: unchanged.
#:
#: **`None` is a real answer, not a missing one.** A playlist group whose members are being fetched
#: as different kinds has no single kind, and inventing one would put a music note on a row that is
#: half video.
MEDIA_KIND_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 23

#: Completion as a fraction from 0 to 1, or `None` when there is nothing honest to draw. `None` is
#: not zero: an unknown total is not "0%", which is a confident lie `Job.progress` already refuses.
PROGRESS_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 6

#: The third line: what this row will be downloaded as, **spelled out** (`T118-R8`, `REQ-009`).
#:
#: Its own role rather than part of `DETAIL_ROLE` because it is the one line that has to survive
#: eliding intact — a truncated format selector is a format selector the user cannot copy, and
#: `REQ-009`'s promise is that they can learn the syntax from it.
SELECTOR_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 9
#: The verbs this row offers, as `Verb` values. Supplied by the model, because *which* verbs a
#: state permits is `row_verbs.verbs_for`'s answer and the model is what knows the job's status —
#: a delegate that derived them from the drawn state text would be reading its own output
#: (`docs/project/TESTING.md` §13). Absent on a surface with no verbs, which draws none.
VERBS_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 10
#: The job this row is about, carried so a verb click can name it. A row index is not an identity:
#: the queue reorders, and `T118-R14` is the record of what an index that outlived its row costs.
JOB_ID_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 11

#: The row's own choice, as a preset name, or `None` for "follows the batch" (`UX-004`).
PRESET_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 7

#: The names the row's editor offers, in order. A model that answers `None` gets no editor at all,
#: which is how the queue uses this delegate without acquiring a control it has no use for.
PRESET_CHOICES_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 8

#: The **text of the chip on the title line**, or nothing for a surface that draws no chip
#: (`T-130`, `T130-R3`).
#:
#: The queue draws one: `UX-005`'s 2026-08-04 amendment adopts the mockup's chip, because a queue is
#: a list of rows in *different* states and the state is what the eye is looking for.
#:
#: **Absent means no**, and that default is why the role survived the surface it was written
#: against. *(This continued "**History does not**, and that is the ruling rather than an omission:
#: every history row is finished, so a chip reading *Done* on all of them is furniture. Absent means
#: no, which is how `HistoryModel` gets the right answer without knowing the role exists." History
#: and `HistoryModel` were removed by `T-169`/`T-170`, so the contrast described a model that no
#: longer exists. The **reasoning** was worth keeping and is why the default is what it is: a model
#: that never sets this role gets the right answer without knowing the role exists — `T-186`.)*
#:
#: **The text, not a flag** (`T130-R3`). It was a `bool`, and the delegate derived the word itself:
#: `PROGRESS_ROLE` when there was a fraction, `STATE_ROLE` otherwise. Both halves were wrong, and
#: neither was fixable here. `UX-005` names the chip's vocabulary — `Done`, `Queued`, `62%`,
#: `Failed` — and it is *not* the status vocabulary: `STATUS_TEXT` says `Completed`, and a
#: completed job also reports a fraction of exactly 1.0, so the chip read `100%` on every finished
#: row. Only the model knows the `JobStatus` that separates "running, so show progress" from
#: "finished, so show the word", and only the model can spell that word compactly enough for a chip.
#: So the model says what the chip reads and the delegate only draws it.
STATE_CHIP_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 13

#: How deep this row sits: `0` for a top-level row, `1` for a playlist's entry (`T-140`).
#:
#: **A depth, not an "is a child" flag**, because the delegate indents by it arithmetically and a
#: boolean would have to be re-read as a number the first time anything nested twice. Absent means
#: zero, which is how every surface that has never heard of groups keeps working unchanged.
DEPTH_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 14

#: Whether this row is a **group** and whether it is open: `True`, `False`, or absent (`T-140`).
#:
#: Absent is the answer for an ordinary row and it is not the same as `False` — `False` means "a
#: playlist, closed", which draws a disclosure triangle, and absent means "not a playlist", which
#: draws none. The same three-valued shape `PRESET_INHERITABLE_ROLE` established at `T126-R4`.
EXPANDED_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 15

#: What the format control says when the row has no single value — a group whose members
#: disagree (`T-157`, `UX-005` amended 2026-08-05). Only the group answers it; a blank
#: control reads as *unset*, which is a different and wronger statement than *they differ*.
PRESET_PLACEHOLDER_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 17

#: One entry of `SegmentState` per playlist entry, for the group's segmented bar (`T-140`,
#: `UX-005` row 9b).
#:
#: **Segments rather than a fraction, and that is the ruling rather than a rendering choice.** The
#: entries' byte totals arrive one at a time, so a percentage across them has a denominator that
#: grows while it runs and a bar that goes *backwards*. A count of blocks only goes up. It also
#: gives a **failed** entry somewhere to be seen: under one continuous bar a playlist that skipped
#: a track looks exactly like one that got everything, which is this feature's characteristic lie.
SEGMENTS_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 16

#: Whether this row has formats to choose from, so the control may offer to open them (`T-108`).
#:
#: **A separate question from `PRESET_CHOICES_ROLE`.** A row can be retargetable and still have no
#: format table — a failed probe, or a playlist, whose formats belong to its entries — and offering
#: an entry that opens an empty table is `UX-005` §5's never-draw-what-would-be-refused again.
#: Absent means no, which is the honest answer from a model that never heard of this role: the
#: queue reuses this delegate and has no probe result to open.
FORMATS_AVAILABLE_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 18

#: How tall this row must be **because its format table is open** (`T-108`, `REQ-008`).
#:
#: Zero or absent means closed, which is every row on every surface until somebody opens one. The
#: height is the panel's own `sizeHint`, asked of the widget rather than guessed at with a constant
#: here — a constant would be a second opinion about how tall a table is, and the first font change
#: would make it the wrong one (`T118-R15`).
FORMAT_PANEL_HEIGHT_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 19

#: The control's entry that opens the format table (`docs/UX_SPEC.md` §4, `UX-007`'s `P-1`).
#:
#: *"The table opens from the format control … through an entry reading `Choose specific formats…`
#: below the preset list."* Below, so the presets keep the positions a user has learned.
CHOOSE_FORMATS_TEXT: Final = "Choose specific formats…"

#: The data this entry carries, which is deliberately **not** a preset name.
#:
#: `setModelData` writes `currentData()` into `PRESET_ROLE`, and any string there is looked up as a
#: preset. A sentinel no preset can be called keeps *"open the table"* from being mistaken for
#: *"set the format to a preset with this name"* — and if the lookup ever did see it, it would find
#: nothing and silently clear the row's format, which is a wrong download rather than a no-op.
CHOOSE_FORMATS_DATA: Final = "\x00open-format-table"

#: Whether this row can have `REQ-010`'s post-processing options set (`T-109`, `UX-SPEC` §6).
#:
#: **A third question, distinct from both roles above.** A row may be retargetable and have no
#: format table (a playlist), and it may have a format table and no business carrying options.
#: Absent means no, which is the honest answer from the queue: a job's request is frozen at
#: creation (`ARCHITECTURE.md` §8), and a control that changed post-processing after the download
#: had started would be one that silently does nothing — `UX-005` §5.
OPTIONS_AVAILABLE_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 20

#: The control's entry that opens the post-processing editor (`docs/UX_SPEC.md` §6's `P-3`).
#:
#: Below `CHOOSE_FORMATS_TEXT` for the same reason that one is below the presets: the entries a
#: user has learned the positions of do not move when a new one appears.
OPTIONS_TEXT: Final = "Options…"

#: Its data, a sentinel for `CHOOSE_FORMATS_DATA`'s reason and with `CHOOSE_FORMATS_DATA`'s
#: consequence if it were ever looked up as a preset name: a silently cleared format, which is a
#: wrong download rather than a no-op.
OPTIONS_DATA: Final = "\x00open-options-editor"

#: Whether this row can have `REQ-011`'s output template edited (`T-112`, `UX-SPEC` §9.1).
#:
#: **A fourth question, and it is `OPTIONS_AVAILABLE_ROLE`'s twin rather than a copy of it.** The
#: template needs no probe result of its own — the preview renders from whatever the row knows and
#: says so where it cannot — but it does need a row that can still be retargeted, for the reason a
#: durable job cannot: its request is frozen at creation (`ARCHITECTURE.md` §8), so an editor there
#: would be a control that silently does nothing. Absent means no.
TEMPLATE_AVAILABLE_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 21

#: The control's entry that opens the output template editor (`docs/UX_SPEC.md` §9.1).
#:
#: Below `OPTIONS_TEXT` for the reason that one is below `CHOOSE_FORMATS_TEXT`: entries a user has
#: learned the positions of do not move when a new one appears.
#:
#: **Renamed from "Where it goes…" on 2026-08-09, maintainer direction.** That label promised a
#: folder picker and opened a `%(field)s` template editor — and the maintainer read it as a
#: destination picker in review, which is the evidence rather than the theory. What it edits is how
#: a download is *named and filed*; **where the root is** becomes `REQ-023`'s download directory,
#: a setting, under `T-146`. Naming the two differently is what keeps them from being confused for
#: each other once both exist.
TEMPLATE_TEXT: Final = "Naming and folders…"

#: Its data, a sentinel for `CHOOSE_FORMATS_DATA`'s reason and with the same consequence if it were
#: ever looked up as a preset name.
TEMPLATE_DATA: Final = "\x00open-template-editor"

#: Whether this surface can open the preset manager (`T-111`, `UX-SPEC` §8).
#:
#: **A fifth question, and the only one that is not about the row.** The four above ask what may be
#: done to *this* download; managing presets edits the catalogue every row chooses from, so the
#: answer depends on whether composition wired a settings store rather than on the row's state.
#: Absent means no, which is the honest answer where there is nowhere to save to — the same rule
#: `OptionsDialog` applies to `Save as preset…` (`UX-005` §5, `P-13`).
PRESETS_MANAGEABLE_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 22

#: The control's entry that opens the preset manager (`docs/UX_SPEC.md` §8's `P-6`).
#:
#: *"A preset manager, reached from the format control's `Manage presets…`"* — the spec names the
#: words. Below the three editors for the reason each of those is below the one before it: the
#: entries a user has learned the positions of do not move when a new one appears.
MANAGE_PRESETS_TEXT: Final = "Manage presets…"

#: Its data, a sentinel for `CHOOSE_FORMATS_DATA`'s reason and with the same consequence if it were
#: ever looked up as a preset name.
MANAGE_PRESETS_DATA: Final = "\x00open-preset-manager"

#: Padding inside the state chip, and its corner radius. Small: it shares the title's line and must
#: not compete with the title for height.
CHIP_PADDING: Final = 5
CHIP_RADIUS: Final = 3

#: Whether this surface **has** a group default a row can defer to (`T126-R4`).
#:
#: The staging list does: `UX-004` gives a paste one format and lets a row override it, so *"same
#: as all"* names a real state the model can store and restore. **A durable queue row does not.**
#: Each job carries its own request and nothing else; the batch it was added with is neither
#: persisted nor reachable, so the entry was a visible control that silently did nothing —
#: `QueueModel.setData` refuses its `None`, and the words were false besides, because there is no
#: "all" on that surface to be the same as. `UX-005` §5: nothing is offered that would be refused.
#:
#: Absent means no, which is how a model that never heard of this role gets the honest answer.
PRESET_INHERITABLE_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 12

#: The name of the preset an unoverridden row would follow, where the surface has one (`UX-004`).
#:
#: **Separate from `PRESET_INHERITABLE_ROLE`, because they answer different questions.** That role
#: says *may this row follow anything* — the gate that keeps the queue, which has no batch, from
#: offering an entry that would do nothing (`T126-R4`). This one says *what it would follow*, and
#: only a surface with a batch can answer it. Folding the name into the gate would make a preset
#: named with an empty string read as "cannot follow".
#:
#: **Absent means the surface has no batch**, which is how a model that never heard of this role
#: gets the honest answer.
MENU_AVAILABLE_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 26
"""Whether this row's `⋮` would open anything (`T315-R2`).

**A painted affordance must have an implemented action for its row kind.** The zone was drawn on
every row carrying a preset control, which on the queue includes a **playlist header** — and a
header's `JOB_ID_ROLE` is the playlist id, which `job_for` cannot resolve, so the menu came back
empty and the press did nothing. The reviewer reproduced it: two grouped jobs gave a dead button
where two ungrouped ones opened a menu.

**Asked of the model rather than inferred here**, because which rows have an item menu is a
property of the surface: the staging list's rows always do, and the queue's group headers never
will while a format id belongs to one video (`T-110`'s rule, one surface over). A delegate deciding
it would be a second opinion about what a row is.

`_menu_zone_of` answers an **empty rectangle** when this is false, which is what makes every
consumer follow from one definition — the combo takes the whole slot back, `contains` refuses every
point, and the paint is skipped.
"""

PRESET_INHERITED_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 25

#: What the editor's inherited entry appends to that name (`UX-004`, ruled 2026-08-30 by the
#: maintainer).
#:
#: **The entry carries the value *and* the relation, and the reason is the click.** The painted
#: control shows the preset's name alone — ruled 2026-08-28, because the relation already lives on
#: the row's detail line and a control that has to hold both elides sooner. If the entry said only
#: the relation, the label the user clicked would not be the entry they see selected: the value
#: would turn into a relation at the moment of the click, which is the defect class `T-283` was
#: built to close. With the value in both, only the suffix appears, and the entry cannot be
#: confused with the preset of the same name one line below it — which pins that preset to this row
#: rather than leaving the row following.
#:
#: The popup has no width constraint, which is why a shape rejected for the control is available
#: here. The wording is the row's own: the detail line already reads *"Download as: … — following
#: the batch"*.
#:
#: *(This was `INHERITED_TEXT = "Same as all"`, in both places, until `T-284`. The maintainer's
#: report was that it *"doesn't make any intuitive sense"*, and it was also a defect against
#: `UX-004` as written, which asks for the preset **and** that it is inherited: the old text
#: delivered the relation and dropped the value. `T118-R4`'s reasoning — never blank, because a
#: blank reads as no format at all — is untouched and is why this is a suffix rather than a
#: replacement.)*
INHERITED_SUFFIX: Final = " — following the batch"


def inherited_entry_text(name: str) -> str:
    """What the editor's `None` entry reads, for the preset `name` the row would follow."""
    return f"{name}{INHERITED_SUFFIX}"


#: The editor's object name. Shared by every row deliberately: they are one control reused, and a
#: test asserting the keyboard surface counts them rather than naming twenty of them.
ROW_PRESET_NAME: Final = "rowPresetChoice"

#: Space around the row's contents.
PADDING: Final = 6

#: The mark an audio row's derived tile carries when there is no artwork yet (`T-217`).
#:
#: **A text glyph, because this one is reliably present.** `QFontMetrics.inFont` says yes for
#: `U+266B` on the base font, which is the same footing the `⋮` stands on (`ARCHITECTURE.md` §8) —
#: it scales with the tile and needs no asset per size.
AUDIO_GLYPH: Final = "\u266b"

#: How opaque the glyph is over its hue block, out of 255 (`T-217`).
#:
#: **Faint enough to be a texture rather than content, opaque enough to survive both grounds.** The
#: block is drawn at HSV value 110 and the glyph at 235, so the glyph is always the lighter of the
#: two and the contrast does not invert between the light and dark palettes — the hue block is this
#: delegate's own ink either way, not the window's.
PLACEHOLDER_GLYPH_ALPHA: Final = 90

#: The glyph's height as a fraction of the tile's, so a child row's smaller slot scales with it.
PLACEHOLDER_GLYPH_SCALE: Final = 0.5

#: The gap between the thumbnail and the text.
GAP: Final = 10

#: How many lines the wrapped literal selector may occupy on the row (`T118-R8`, `T118-R15`).
#:
#: **The row shows as much of the selector as fits in these lines; the complete, copyable value
#: lives below the list.** That split is the contract, and it is narrower than the one this
#: constant used to claim. Two lines holds the longest built-in at the default 9 pt font — and
#: `T118-R15` measured the same string needing three lines at 12 to 15 pt and five at 18 pt, so a
#: promise that the row never clips was true only of the font the tests happened to use.
#:
#: Sizing the row from the wrapped height instead would make row height depend on content, and
#: uniform rows are what let a long list compute its visible range arithmetically rather than
#: measuring every row — the property `T118-R10` turns on. So the row stays uniform and
#: `add_dialog`'s `selectorValue` label, which wraps freely and is selectable, is the surface that
#: carries the whole value at any font.
SELECTOR_LINES: Final = 2

#: How many lines of text a row draws: headline, detail and state, then the selector's own lines.
#:
#: **The row's anatomy, and a failed row is one line taller** (`T201-R3`, ruled 2026-08-14). That
#: line is `ACTION_ROLE`'s and is counted by `_action_lines` rather than folded in here, because
#: it is spent per row: every row that has not failed, and every failure with no honest action, is
#: drawn at exactly this height.
TEXT_LINES: Final = 2 + SELECTOR_LINES

#: **The row is at least as tall as the thumbnail it contains** (`T118-R7`). Derived rather than
#: chosen, so changing `THUMBNAIL_SIZE` cannot leave a 54 px picture in a 25 px row again.
#:
#: A floor rather than the final answer: `sizeHint` takes the larger of this and the height
#: `TEXT_LINES` actually need in the view's font, because a user running a large font would
#: otherwise get three lines clipped into a box sized for a picture — the same defect as `R7`,
#: arrived at from the other side.
ROW_HEIGHT: Final = THUMBNAIL_SIZE[1] + 2 * PADDING

#: How wide the row's editor is drawn. Wide enough for the longest preset name plus its arrow.
EDITOR_WIDTH: Final = 190

#: The narrowest the format control is drawn before it stops narrowing (`T-160`).
#:
#: **The control narrows; it is never withheld and never drawn over the picture.** That is the
#: promise, stated because a control that silently shrinks and one that silently vanishes are
#: different ones. Withholding was the alternative and was rejected: the `⋯` exists so a dropped
#: verb is still reachable, and there is no equivalent for the format — `EDIT_KEY` opens an editor
#: in this very rectangle, so a row that withheld it would have no route to the format at all.
#:
#: The number is the combo's arrow plus enough of the name to tell one choice from another. Below
#: it the control reads as a button with no label, which looks broken rather than narrow.
MIN_CONTROL_WIDTH: Final = 64

#: What the row's first two lines keep before the control stops taking width from them (`T-160`).
#:
#: The headline is the row's identity and `HEADLINE_ROLE` is the one thing every surface answers —
#: "a row nobody can identify is worse than a long URL". This is enough for a recognisable prefix
#: of one. It is a preference, not a floor: `MIN_CONTROL_WIDTH` wins on a row too narrow for both,
#: because a control that has shrunk out of existence is worse than a title that has been elided.
MIN_TEXT_WIDTH: Final = 120

#: The height of the painted progress bar.
BAR_HEIGHT: Final = 4

#: The gap between two blocks of a group's segmented bar (`T-155`, `T-167`).
#:
#: **Uniform at every width, and a constant rather than a calculation.** It used to collapse to
#: zero on a narrow bar, and sixteen blocks touching are one bar to the eye — which is what the
#: maintainer reported as the bar "becoming a single bar" as the window narrowed. `T-155` was
#: blocks merging *by accident*; `UX-005` row 9b-i's constraint is that a bar which merges on
#: purpose must not be mistakable for that defect returning, so the gap does not vary.
SEGMENT_GAP: Final = 1

#: A height no wrapped text reaches, for measuring how many lines a string takes at a given width.
_UNBOUNDED: Final = 1 << 20

#: The narrowest a block may be drawn and still read as an entry rather than as noise (`T-164`).
#:
#: **The number is the decision** (`T118-R8`), so it is stated here rather than tuned by eye. It
#: is anchored to the measurement that opened `T-164`: sixteen blocks in a 200 px bar are twelve
#: pixels each, and at that size the segmentation "reads as noise rather than as information". So
#: the floor sits above twelve rather than at it.
#:
#: Everything the last line decides is derived from this one number — when the blocks merge
#: (`T-164`), and how much of the line the bar keeps from the verbs (`T-163`).
MIN_BLOCK_WIDTH: Final = 16

#: How many blocks a bar draws once its entries no longer each fit (`UX-005` row 9b-i, `T-164`).
#:
#: **What this gives up is stated rather than glossed: a block stops meaning an entry.** The
#: maintainer's first suggestion was one solid *done of total* bar and was **rejected**, because it
#: moves the failure out of the drawing and into the text — which is the shape row 9b was adopted
#: against. Merging keeps the failure visible and spends the weaker guarantee instead, and it is
#: only affordable because the count is carried exactly elsewhere: the chip reads `4 of 16`
#: (row 9a) and the second line names each ending.
MERGED_BLOCKS: Final = 8

#: How the selector's line is laid out — **one definition, drawn and measured through the same
#: value** (`T-150`). `minimum_row_width` asks how wide that line must be for a given selector, and
#: an answer computed under different wrapping flags than the paint uses would size a window for
#: text the row lays out some other way.
SELECTOR_FLAGS: Final = int(
    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap
)

#: The narrowest a plain fraction bar may be drawn (`T-163`).
#:
#: **Less than a segmented bar needs, because it has less to show** — one position along its length
#: rather than sixteen endings. Derived rather than picked: a quarter is the coarsest reading
#: anybody takes off a progress bar, and a quarter of this is one legible block.
MIN_FRACTION_BAR: Final = 4 * MIN_BLOCK_WIDTH

#: Which state a merged block takes when it covers several entries, worst first (`T-164`).
#:
#: **A covered failure must not be outvoted by three successes** — that is row 9b's whole
#: guarantee and it does not bend at a narrow window. Below the two endings, the order is
#: least-advanced first, so a block never claims more progress than the slowest entry it covers:
#: over-reporting is the lie a merged bar is most able to tell.
_WORST_FIRST: Final = (
    SegmentState.FAILED,
    SegmentState.CANCELLED,
    SegmentState.WAITING,
    SegmentState.RUNNING,
    SegmentState.DONE,
)

#: How far one level of nesting indents a row, and the width reserved for the disclosure
#: triangle (`T-140`). The triangle sits in the indent a group's own children get, so a group and
#: its entries line up on the same left edge rather than stepping twice.
INDENT: Final = 22
TWISTY_WIDTH: Final = 14

#: A child row's thumbnail, and the lines it draws. **Shorter, not merely indented** (`UX-005`
#: row 9c): an entry inherits the group's format, so the third and fourth lines have nothing to
#: say, and a smaller tile buys back the width the indent costs.
CHILD_THUMBNAIL: Final = (38, 22)
CHILD_TEXT_LINES: Final = 2

#: Padding inside a verb button, each side. Small: they share the last line with the progress bar
#: and `NFR-006` wants the message above them at full width.
VERB_PADDING: Final = 8

#: The gap between adjacent verb buttons.
VERB_GAP: Final = 4

#: How tall the row's format control is drawn. A combo box's own height, near enough, and bounded
#: by the row so a large font cannot push it outside its own row.
CONTROL_HEIGHT: Final = 26

#: The width of the `⋮` zone on the trailing edge of the row's format control (`T-203`, `UX-011`).
#:
#: **Fixed, not proportional.** The zone is a painted affordance for the row's menu, and one that
#: grew with the control would take its width from the preset name — the one thing `UX-004` says
#: must stay readable. At `MIN_CONTROL_WIDTH` the combo half keeps three quarters of the control.
MENU_ZONE_WIDTH: Final = 16

#: What the zone draws. A vertical ellipsis, deliberately distinct from the queue's `⋯` overflow:
#: that one *is* a button with actions of its own, this one is a door to the row's menu.
MENU_ZONE_GLYPH: Final = "⋮"

#: How far the button face is inset from the control's full height, and its corner radius
#: (`T-224`). Inset so the door reads as a control *on* the row rather than as a second frame
#: butted against the combo's; a radius so it matches the platform's own button corners rather
#: than being the one square thing on the row.
MENU_ZONE_INSET: Final = 3
MENU_ZONE_RADIUS: Final = 2

#: **The declared keyboard route to a row's editor** (`T118-R9`).
#:
#: Stated here rather than left to `QAbstractItemView`'s default, because "the row controls are
#: outside the declared focus order" was the finding, and a route that exists only as a Qt default
#: is a route nobody declared. The view sets `EditKeyPressed`, which is this key.
EDIT_KEY: Final = Qt.Key.Key_F2

#: What that route is called on screen and to a screen reader. One sentence, in one place, so the
#: dialog's help text and the delegate's accessible description cannot drift apart.
EDIT_HINT: Final = "Press F2 to choose a format for this row."


def _depth(index: QModelIndex | _PersistentIndex) -> int:
    """How deep a row sits, treating an absent role as top level (`T-140`)."""
    depth = index.data(DEPTH_ROLE)
    if isinstance(depth, bool) or not isinstance(depth, int) or depth < 0:
        return 0
    return depth


def _action_lines(index: QModelIndex | _PersistentIndex) -> int:
    """How many lines this row spends on `ACTION_ROLE` — one, or none (`T201-R3`).

    **The one place the question is answered**, so `sizeHint`, `_paint_text` and `_verb_rects`
    cannot hold three opinions about how tall the row is. That is `_control_rect`'s rule applied to
    a height rather than a rectangle, and `T-140`'s child row is the record of what a `sizeHint`
    and a painter disagreeing about a line costs: the text was drawn into space the row did not
    have and was clipped.
    """
    return 1 if _text(index, ACTION_ROLE) else 0


def _text_lines(index: QModelIndex | _PersistentIndex) -> int:
    """How many lines of text this row draws — **the one answer the whole row is built from**.

    `sizeHint` measures it, `_paint_text` lays out against it, and `_verb_rects` puts the buttons on
    the last of them. That is the point of it being a function: those three used to derive the
    number separately, and `T-244` is what the disagreement cost. `sizeHint` shortened a playlist
    entry to `CHILD_TEXT_LINES` while the verb layout went on measuring every row from the
    top-level `TEXT_LINES` — so a child's last line was computed *below its own body*, the layout
    returned no rectangles at all, and **an expanded entry offered `Retry` and `Remove` and drew
    neither**. Not a clipped control, which is visible: no control.

    The conditional lines are conditional for the reason `UX-005` row 9c gives — height goes where
    the row has something more to say, and nowhere else. An entry states a format only when it
    differs from its group (`T-157`), and any row states a next step only when the failure has an
    honest one (`T201-R3`).
    """
    action = _action_lines(index)
    if _depth(index) > 0:
        return CHILD_TEXT_LINES + (1 if _text(index, SELECTOR_ROLE) else 0) + action
    return TEXT_LINES + action


def _segments(index: QModelIndex | _PersistentIndex) -> tuple[SegmentState, ...]:
    """The group's per-entry states, or empty for a row that is not a group (`T-140`)."""
    raw = index.data(SEGMENTS_ROLE)
    if not raw:
        return ()
    states: list[SegmentState] = []
    for value in raw:
        try:
            states.append(SegmentState(value))
        except ValueError:
            # A state this delegate does not know is drawn as waiting rather than dropped: a bar
            # with fewer blocks than the playlist has entries would misreport the size of the work.
            states.append(SegmentState.WAITING)
    return tuple(states)


def segment_span(blocks: int) -> int:
    """The narrowest a bar of `blocks` blocks may be drawn (`T-164`, `T-167`).

    One arithmetic, so the width the bar asks the verbs for and the width its rendering is chosen
    against cannot disagree — the same rule `_control_rect` and `_verb_rects` follow about a thing
    drawn in one place and measured in another.
    """
    return max(blocks, 0) * MIN_BLOCK_WIDTH + max(blocks - 1, 0) * SEGMENT_GAP


def selector_line_width(metrics: QFontMetrics, text: str) -> int:
    """The narrowest the selector's line can be and still hold `text` in `SELECTOR_LINES` (`T-150`).

    **Measured through Qt's own wrapping rather than divided out of the string's width.** A
    selector is one long unbreakable-looking token after a run of ordinary words, so the width it
    needs is not its total over the number of lines: `bestvideo[height<=1080][ext=mp4]+…` alone
    measures 489 px at the default font and that, not the arithmetic mean, is what sets the answer.

    Searched rather than solved because `boundingRect` is the only thing that knows where Qt will
    break a string, and it is the same call the paint's layout comes from.
    """
    if not text:
        return 0
    room = SELECTOR_LINES * metrics.height()
    low, high = 1, max(metrics.horizontalAdvance(text), 1)
    while low < high:
        middle = (low + high) // 2
        box = metrics.boundingRect(QRect(0, 0, middle, _UNBOUNDED), SELECTOR_FLAGS, text)
        if box.height() <= room:
            high = middle
        else:
            low = middle + 1
    return low


def minimum_row_width(
    metrics: QFontMetrics,
    selectors: Sequence[str] = (),
    *,
    tile: int = THUMBNAIL_SIZE[0],
) -> int:
    """The narrowest a row can be drawn with nothing in its anatomy giving way (`T-150`).

    **Derived from the delegate's own metrics, so a surface sized by it cannot fall behind them.**
    `ROW_HEIGHT` is computed from `THUMBNAIL_SIZE` for the same reason — *"so changing
    `THUMBNAIL_SIZE` cannot leave a 54 px picture in a 25 px row again"* — and a window with a
    number typed into it would go stale the first time one of these constants moved.

    Two things set it, and the larger wins:

    - **The first two lines**, where the tile, the text and the format control share the width.
      This is exactly the point at which `_control_rect` stops giving `EDITOR_WIDTH` and starts
      narrowing (`T-160`), so the row below it is a row whose control has already begun to give.
    - **The selector's line**, for the widest string the caller says it can be asked to draw.
      `SELECTOR_LINES` is sized so two lines hold the longest built-in at the default font, and
      that promise is about a row with the room to keep it.

    Callers pass the strings *their* surface can produce, rather than this guessing: the staging
    list's come from the preset catalogue it was given, which is injectable.
    """
    anatomy = 2 * PADDING + tile + GAP + MIN_TEXT_WIDTH + GAP + EDITOR_WIDTH + 1
    widest = max((selector_line_width(metrics, text) for text in selectors), default=0)
    return max(anatomy, 2 * PADDING + tile + GAP + widest + 1)


def segment_blocks(entries: int, line_width: int) -> int:
    """How many blocks a bar of `entries` entries draws on a line this wide (`T-164`, `T-167`).

    **One threshold, one number, and the input moves one way.** Below it the entries merge into
    `MERGED_BLOCKS`; above it there is one block per entry, which is what `T-155` guards. Merging
    is skipped where it would not help — a playlist of six drawing eight blocks would invent two.
    """
    if entries <= MERGED_BLOCKS or segment_span(entries) <= line_width:
        return entries
    return MERGED_BLOCKS


def _fraction(index: QModelIndex | _PersistentIndex) -> float | None:
    """The row's completion, or `None` when there is nothing honest to draw.

    `None` is not zero: an unknown total is not "0%", which is a confident lie `Job.progress`
    already refuses. `bool` is excluded because it is an `int` in Python and `True` would draw a
    full bar.
    """
    value = index.data(PROGRESS_ROLE)
    if isinstance(value, bool) or not isinstance(value, float | int):
        return None
    return float(value)


def _merge(states: Sequence[SegmentState], blocks: int) -> tuple[SegmentState, ...]:
    """Fold `states` into `blocks`, each taking the worst state it covers (`UX-005` row 9b-i).

    **Each block ends where the next begins**, the same arithmetic `_paint_segments` uses on the
    pixels and for the same reason: two independent roundings would let one entry be covered twice
    or by nothing, and an entry no block covers is a failure with nowhere to be seen.
    """
    if blocks >= len(states) or blocks <= 0:
        return tuple(states)
    return tuple(
        min(
            states[position * len(states) // blocks : (position + 1) * len(states) // blocks],
            key=_WORST_FIRST.index,
        )
        for position in range(blocks)
    )


class RowDelegate(QStyledItemDelegate):
    """Draws a rich row, and opens **one** editor for the row being edited.

    The store is optional: a surface with no thumbnails to draw passes none and gets the derived
    tile for every row, which is exactly what an unresolved staging row wants anyway.
    """

    #: A row's verb was activated. Carries the job id rather than a row index — the queue
    #: reorders, and `T118-R14` is this project's record of what an index outliving its row costs.
    #: `None` for the verb means the overflow was asked for.
    verb_triggered = Signal(str, object)

    #: A group row's disclosure was operated (`T-140`). Carries the row's id, because a row number
    #: stops naming the same thing the moment the queue reorders — `T126-R1`'s lesson, and the
    #: reason `JOB_ID_ROLE` exists at all.
    #:
    #: **The delegate reports, it does not decide.** Which rows are visible is the model's, and a
    #: delegate that expanded a group by editing the list it draws would be two places deciding
    #: what a row is.
    disclosure_toggled = Signal(str)

    #: The row's `⋮` zone was clicked (`T-203`, `UX-011` option *E*). Carries the click's viewport
    #: position rather than a row id, because the receiver is the same slot the context-menu
    #: routes already use — it resolves the row from the point, so the two doors cannot resolve
    #: it differently.
    menu_requested = Signal(object)

    def __init__(
        self,
        *,
        thumbnails: ThumbnailStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._thumbnails = thumbnails
        #: The row whose live editor is open, or `None`. At most one at a time — that is the whole
        #: of `T118-R10`'s correction, and `_paint_control` reads it to avoid drawing the
        #: affordance underneath the real control.
        self._editing_row: int | None = None
        #: The verb under the pointer, as `(row, verb)`, or `None` (`T-134`).
        #:
        #: **By row number rather than by job id, and that is deliberate here** even though
        #: `T126-R1` made the editor's identity a job id. A hover is recomputed on the next mouse
        #: move and discarded on a reset; it never has to survive anything. The staging list has no
        #: job ids at all, and the verbs are drawn there too.
        self._hovered: tuple[int, Verb | None] | None = None
        #: Which row's `⋮` zone is held down, or `None` (`T-224`). Cleared when the press is
        #: released or leaves, so a menu opened by the press does not leave the zone stuck sunken.
        self._pressed_zone: int | None = None
        #: Which row's `⋮` zone the pointer is over, or `None` (`T-224`, `UX-012`).
        #:
        #: **Separate from `_hovered`**, which is keyed by `Verb` and belongs to the queue's verb
        #: buttons. The zone is not a verb — it has no `Verb` member and lives on the *staging*
        #: row's format control — so folding it into that tuple would mean inventing a sentinel
        #: member for something that is not one.
        self._hovered_zone: int | None = None
        #: What each row's last paint could **not** fit, by job id (`T-135`). The `⋯` menu's
        #: contents; see `overflowing` for why this is a record rather than a recomputation.
        self._dropped: dict[str, tuple[Verb, ...]] = {}
        #: The live editor itself, so it can be committed and closed **before** a model reset
        #: invalidates its index (`T118-R14`).
        self._editor: QWidget | None = None
        #: **Which row that is, by identity rather than by position** (`T126-R1`). A row number
        #: survives a reset as a number and stops naming the same job the moment the queue
        #: reorders, so a caller reopening the editor after a rebuild has to ask for the *job*.
        #: `None` on a surface whose model answers no `JOB_ID_ROLE` — the staging list, whose rows
        #: have no job behind them yet — which is why nothing here requires one.
        self._editing_job_id: str | None = None

    # --- size and drawing -----------------------------------------------------------------

    # Qt's override names, hence the camelCase: these are not project naming choices.
    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex | _PersistentIndex
    ) -> QSize:
        """How tall a row is: one height for ordinary rows, a shorter one for a playlist's entry.

        **It used to be genuinely uniform, and that was worth something** — uniform rows let the
        view compute the visible range arithmetically instead of measuring every one, which is the
        same reason `setUniformItemSizes` existed on the list this delegate replaced, and
        `T118-R10` is the record of what per-row cost buys when it goes wrong.

        `UX-005` row 9c spends it deliberately. An entry inherits its group's format, so its third
        and fourth lines have nothing to say; drawing it at full height to keep the promise would
        waste a third of the list on blank space in exactly the case — a sixteen-item playlist —
        where there is least room to waste. **The measurement that justifies the trade is
        `T-140`'s own acceptance criterion**, not an assumption made here.

        **A row with its format table open is taller still** (`T-108`). At most one row is open at a
        time, so this is one measured row among however many, not a per-row cost.

        **And a failed row with something to suggest is one line taller** (`T201-R3`, ruled
        2026-08-14). Spent on the same rule the entry's format line is spent on — height goes where
        the row has an additional fact — and taken from `_action_lines`, which is also what the
        painter and the verb layout ask, so the row cannot be sized for one anatomy and drawn in
        another.
        """
        open_panel = index.data(FORMAT_PANEL_HEIGHT_ROLE)
        if isinstance(open_panel, int) and open_panel > 0:
            # The height comes from the panel's own `sizeHint` — see `FORMAT_PANEL_HEIGHT_ROLE` for
            # why it is asked for rather than assumed.
            return QSize(option.rect.width(), open_panel)
        # **Three lines when the entry has a format of its own to state** (`T-157`), two otherwise.
        # `UX-005`'s amendment spends the line exactly where there is something to say, so a
        # uniform playlist — every playlist until somebody retargets a part-done one — is drawn at
        # the height row 9c bought. `_text_lines` is that rule, and it is the same call the paint
        # and the verb layout make (`T-244`).
        text = _text_lines(index) * option.fontMetrics.height() + 2 * PADDING
        if _depth(index) > 0:
            return QSize(option.rect.width(), max(CHILD_THUMBNAIL[1] + 2 * PADDING, text))
        return QSize(option.rect.width(), max(ROW_HEIGHT, text))

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | _PersistentIndex,
    ) -> None:
        """Draw the whole row: tile or picture, headline, detail, state, and progress.

        **The only place a thumbnail is ever asked for.** `ThumbnailStore.pixmap` starts a fetch on
        a miss, so a row the view never paints never causes a request — which is `T-119`'s
        criterion satisfied by where the call sits rather than by a rule someone maintains.
        """
        style_option = QStyleOptionViewItem(option)
        self.initStyleOption(style_option, index)
        # The text is drawn by hand below, so Qt must not also draw it underneath.
        style_option.text = ""

        # Qt's stubs type `widget` as a `QWidget`, while a style option built outside a view really
        # does carry `None` — the same mismatch `add_dialog._row_preset_control` documents. `cast`
        # states the real contract here rather than suppressing the check at the branch.
        widget = cast("QWidget | None", style_option.widget)
        if widget is not None:
            widget.style().drawControl(
                QStyle.ControlElement.CE_ItemViewItem, style_option, painter, widget
            )

        painter.save()
        painter.setClipRect(option.rect)

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        palette = option.palette
        primary = palette.highlightedText().color() if selected else palette.text().color()
        muted = QColor(primary)
        muted.setAlpha(170)

        # **A playlist and its entries** (`T-140`, `UX-005` rows 9 and 9c). The disclosure sits in
        # the same indent the children get, so a group and its entries share a left edge instead
        # of stepping twice; and a child's tile is smaller, because an entry inherits its group's
        # format and has two lines to say rather than four.
        #
        # Drawn against the *unindented* body, which is where `_twisty_rect` hit-tests it.
        expanded = index.data(EXPANDED_ROLE)
        # **Only the closed state is painted** (`T-210`). An opened row is covered by its panel, and
        # the panel carries its own disclosure — the way out has to be a real widget, because the
        # painting underneath it is not reachable and has no accessibility node. Drawing the open
        # triangle here as well put **two arrows side by side** on every expanded row.
        #
        # `EXPANDED_ROLE` still answers all three values and `sizeHint` still reserves the width for
        # any of them, so the row's anatomy does not shift when it opens (`T-140`).
        if expanded is False:
            self._paint_twisty(
                painter,
                option.rect.adjusted(PADDING, PADDING, -PADDING, -PADDING),
                muted,
                opened=False,
            )
        if _depth(index):
            self._paint_rail(painter, option.rect, muted)

        # **The same body and the same text area the click and the hover resolve** (`T-160`). The
        # two were computed separately and disagreed about the indent, which did not show while
        # the control was anchored to the right edge alone and would have the moment it started
        # measuring from the row's left.
        body, text_area = self._verb_area(option, index)
        _, tile = self._body_of(option, index)
        self._paint_tile(painter, body, index, size=tile)

        # **The control is drawn on every row that has one** (`UX-004` §1, `T118-R12`). Reserving
        # the slot and painting nothing in it was the defect: an empty 190 px gap is not a visible
        # control, and it left the override discoverable only by knowing it was there.
        #
        # Drawn rather than instantiated, which is `UX-004`'s own sequencing note ("C") — the live
        # `QComboBox` still exists only for the row being edited, so the widget-per-row cost that
        # `T118-R10` measured does not come back. What the user sees is identical either way,
        # because both are drawn by the same style.
        #
        # Suppressed only under the live editor, which occupies the same rectangle — otherwise the
        # painted affordance shows through the real control's edges.
        if self._editable(index):
            # **The zone outlives the editor; the combo does not** (`T-314`). They shared this one
            # condition, so opening the dropdown erased the `⋮` beside it — see `_paint_menu_zone`.
            if not self._is_being_edited(index):
                self._paint_control(painter, option, index)
            if index.data(MENU_AVAILABLE_ROLE):
                self._paint_menu_zone(painter, option, index)

        verbs_left = self._paint_verbs(painter, text_area, body, option, index)
        self._paint_text(
            painter, text_area, body, index, primary, muted, verbs_left, option.palette
        )
        painter.restore()

    def _control_rect(self, body: QRect, line: int = 0, *, tile: int = THUMBNAIL_SIZE[0]) -> QRect:
        """Where the row's format control sits. One definition, so the painted affordance, the
        live editor and the click target cannot disagree about where it is.

        **Beside the first two lines, not centred in the row** (`T-136`). It was centred in the
        whole body, and `_paint_text` runs the selector at the *full* body width on the stated
        reasoning that "the control sits beside the first two lines, and nothing needs the third
        line's right-hand end". On a four-line row, centred is not beside lines one and two — it
        is across line three, and the format selector `REQ-009` promises the user can read ran
        underneath it. Measured before the fix: control `QRect(563, 35, 190, 26)` against selector
        `QRect(112, 57, 642, 34)`, intersecting.

        **The selector is the half that could not give.** Narrowing it back to the leftover width
        beside the control is `T118-R8` exactly — the defect where `REQ-009`'s selector was elided
        into uselessness — so the control moved instead, which also makes the older comment true
        rather than leaving two correct halves that contradict each other.

        **It narrows before the picture; it never crosses it** (`T-160`). The left edge was clamped
        to `body.left()`, which is where `_paint_tile` draws the thumbnail — so a row narrower than
        roughly 300 px drew *Same as all* across the picture. Visible at the size the add dialog
        opens at, so every user met it before they met anything else.

        **This is `T-136`'s family, one collision over**, and it gets the same answer from the
        other side: there the control moved because the selector could not give, and here it
        narrows because the picture cannot. What it gives up is `MIN_TEXT_WIDTH` first and then its
        own width down to `MIN_CONTROL_WIDTH` — stated at those constants, because a control that
        silently shrinks and one that silently vanishes are different promises and this one shrinks.

        `line` is the font's line height; `0` keeps the old centring for a caller that has no
        metrics to hand, and every caller in this module has them. `tile` is the picture it must
        stay clear of, which is smaller on a playlist's entry than on an ordinary row.
        """
        height = min(CONTROL_HEIGHT, body.height())
        band = min(2 * line, body.height()) if line else body.height()
        beside = max(body.right() - (body.left() + tile + GAP), 0)
        width = min(
            max(min(beside - MIN_TEXT_WIDTH - GAP, EDITOR_WIDTH), MIN_CONTROL_WIDTH), beside
        )
        return QRect(
            body.right() - width,
            body.top() + max(band - height, 0) // 2,
            width,
            height,
        )

    def _body_of(
        self, option: QStyleOptionViewItem, index: QModelIndex | _PersistentIndex
    ) -> tuple[QRect, tuple[int, int]]:
        """The row's body once its indent is taken out, and the tile that sits at its left edge.

        **One definition, because two of them disagreed** (`T-160`). `paint` indented the body for
        a group's disclosure and for a child's nesting; `_verb_area`, which the click and the hover
        resolve against, did not. Nothing showed while every rectangle was measured from the row's
        *right* edge — the indent does not move that — and the first thing measured from the left
        would have been drawn in one place and clicked in another.
        """
        body = option.rect.adjusted(PADDING, PADDING, -PADDING, -PADDING)
        depth = _depth(index)
        indent = (
            depth * INDENT
            if depth
            else (TWISTY_WIDTH if isinstance(index.data(EXPANDED_ROLE), bool) else 0)
        )
        if indent:
            body = QRect(
                body.left() + indent,
                body.top(),
                max(body.width() - indent, 0),
                body.height(),
            )
        return body, (CHILD_THUMBNAIL if depth else THUMBNAIL_SIZE)

    def _control_of(
        self, option: QStyleOptionViewItem, index: QModelIndex | _PersistentIndex
    ) -> QRect:
        """Where this row's control sits, resolved from the row itself (`T-160`).

        The paint, the click and the editor's geometry all come through here, so none of them can
        hold a different idea of the row's indent or of the tile the control has to clear.
        """
        body, tile = self._body_of(option, index)
        return self._control_rect(body, option.fontMetrics.height(), tile=tile[0])

    @staticmethod
    def _label_box(
        box: QStyleOptionComboBox, style: QStyle, widget: QWidget | None
    ) -> QStyleOptionComboBox:
        """`box` shifted so `CE_ComboBoxLabel` draws where the real editor would (`T-283`).

        Only the label pass uses this: the frame and the arrow are already drawn from the true
        rectangle, and moving those would move the control rather than its text.
        """
        field = style.subControlRect(
            QStyle.ComplexControl.CC_ComboBox, box, QStyle.SubControl.SC_ComboBoxEditField, widget
        )
        wanted = (
            box.rect.x()
            + style.pixelMetric(QStyle.PixelMetric.PM_ComboBoxFrameWidth, box, widget)
            + theme.COMBO_PADDING_X
        )
        shifted = QStyleOptionComboBox(box)
        shifted.rect = box.rect.adjusted(wanted - field.x(), 0, 0, 0)
        return shifted

    @staticmethod
    def _label_field(box: QStyleOptionComboBox, style: QStyle, widget: QWidget | None) -> QRect:
        """The rectangle `CE_ComboBoxLabel` actually paints text into (`T284-R2`).

        **Not the control's rect, and not the rect with the `⋮` zone removed** — those are 190 and
        174 px at the row geometry the regressions use, and Qt paints into roughly 146. The frame,
        the arrow and `T-283`'s inset all come out of it, which is why this asks the style through
        the same `_label_box` the paint pass uses rather than doing the arithmetic a second way.

        **The number is the style's, not this module's** (`T284-R4`): ~146 px offscreen with no
        widget, 148 through the production dark sheet on a real one. Callers must ask rather than
        assume, which is the point of this existing at all.

        The first version of `T-284`'s elision regression measured the outer rectangle and so
        passed while the shipped label truncated.
        """
        return style.subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            RowDelegate._label_box(box, style, widget),
            QStyle.SubControl.SC_ComboBoxEditField,
            widget,
        )

    def _menu_zone_of(
        self, option: QStyleOptionViewItem, index: QModelIndex | _PersistentIndex
    ) -> QRect:
        """Where the row's `⋮` zone sits: the trailing slice of the control (`T-203`, `UX-011`).

        **Carved out of `_control_of`, never measured beside it**, so the paint, the click and
        the combo's remaining room cannot disagree about where the control ends and the zone
        begins. This is the delegate's paint-and-hit-test seam — `T107-R2`, `T108-R2` and
        `T-204` are its record — which is why the zone has one definition and its own regression.
        """
        if not index.data(MENU_AVAILABLE_ROLE):
            # **No menu, no zone** (`T315-R2`). Empty is the answer that carries: `contains`
            # refuses every point, `_combo_rect` gives the control its full slot back, and `paint`
            # skips the glyph — so one check here settles the paint, the hover and both hit-tests
            # rather than four that could disagree.
            return QRect()
        control = self._control_of(option, index)
        return QRect(
            control.right() - MENU_ZONE_WIDTH + 1,
            control.top(),
            MENU_ZONE_WIDTH,
            control.height(),
        )

    def _combo_rect(
        self, option: QStyleOptionViewItem, index: QModelIndex | _PersistentIndex
    ) -> QRect:
        """Where the **Download as** combo goes: the control slot, less the `⋮` zone (`T-314`).

        **`T118-R12`'s rule, which the zone had quietly broken.** That correction gave the painted
        affordance and the live editor one rectangle *"so the control does not move at the moment
        the user clicks it"* — then `T-203` carved the zone out of the paint side only. The editor
        went on taking the whole slot, so clicking the combo grew it by `MENU_ZONE_WIDTH` and it
        landed **on top of the `⋮`**: reported from the built window as *"when you click on the
        drop down, the button completely disappears."*

        Both callers ask here now, which is what makes the rule true rather than stated.
        """
        control = self._control_of(option, index)
        return control.adjusted(0, 0, -self._menu_zone_of(option, index).width(), 0)

    def _verbs_of(self, index: QModelIndex | _PersistentIndex) -> tuple[Verb, ...]:
        """What the model says this row offers. Empty on a surface that offers nothing."""
        offered = index.data(VERBS_ROLE)
        if not offered:
            return ()
        return tuple(Verb(value) for value in offered)

    def _verb_rects(
        self,
        metrics: QFontMetrics,
        area: QRect,
        body: QRect,
        index: QModelIndex | _PersistentIndex,
    ) -> list[tuple[Verb | None, QRect]]:
        """Where each verb sits on the row's last line, right-aligned (`UX-005` §4).

        **One definition, shared by the paint and the click**, for `_control_rect`'s reason: a
        button drawn in one place and hit-tested in another is a control that works where nobody
        clicks. `T118-R12` is the same lesson from the other direction.

        Laid out right to left from the end of `area` — which is already narrowed by the format
        control's slot when the row has one, so the verbs and the control cannot overlap. When the
        overflow is needed it is rightmost, so its position does not move as the state changes.

        **`⋯` appears only when the row could not show everything** (`T-135`, `UX-005` row 8). It
        used to be unconditional, on the reasoning that it was the keyboard route and a route that
        relocates is not a route — which was true when it was written and stopped being true at
        `T124-R1`, when both lists took `CustomContextMenu`. Qt raises `customContextMenuRequested`
        for the Menu key and Shift+F10, so the keyboard route is the context menu and does not
        depend on this button existing. What the unconditional `⋯` did instead was offer a menu of
        the same three actions the row was already showing.

        Returns rightmost-first, which is also the order a hit test wants: verbs are laid out
        without gaps between their hit rects, so first match wins and it should be the one drawn
        on top if they ever did overlap.
        """
        offered = self._verbs_of(index)
        if not offered:
            # **No verbs means nothing at all, not a lone overflow.** The add dialog's staging
            # rows have no job behind them and nothing to act on; drawing `⋯` there would offer a
            # menu of nothing, and it moved the row's text depending on whether the row happened
            # to have a format control — which is `T118-R8` again.
            return []

        line = metrics.height()
        # **The row's own last line, whichever line that is** (`T201-R3`, `T-244`). A failed row
        # with an action to offer is one line taller and the buttons move down with it; a playlist
        # entry is *shorter* and they have to move up. Both come from `_text_lines`, because the
        # two anatomies were derived separately here and in `sizeHint` — and the child case put
        # this baseline below the row's own body, so `height` clamped to zero and every entry
        # silently drew no verbs at all.
        top = area.top() + (_text_lines(index) - 1) * line
        height = min(line, max(body.bottom() - top, 0))
        if height <= 0:
            return []

        # **The bar's share of the line is taken out first** (`T-163`). The verbs used to be laid
        # out against the whole of `area` and the bar took whatever was left, which at a narrow
        # window was a stub — `Open` and `Show in folder` at full width above a bar of nine pixels.
        #
        # The gap is part of the limit rather than of the reserve: `_paint_verbs` stops the bar
        # `VERB_GAP` short of the leftmost button, so a limit without it hands the bar four pixels
        # less than it asked for and its blocks come out one under `MIN_BLOCK_WIDTH`. Measured at
        # a 758 px window before this was added — sixteen blocks, three of them 15 px.
        reserve = self._bar_reserve(metrics, area, index)
        limit = area.left() + reserve + (VERB_GAP if reserve else 0)
        whole = self._lay_out(offered, metrics, area, top, height, limit, overflow=False)
        # **Tried twice, because reserving the overflow costs width that might be what made it
        # necessary.** Laying out with `⋯` always present would drop the leftmost verb on a row
        # where all of them would have fitted without it — the button would then be needed only
        # because it was there.
        if len(whole) == len(offered):
            return whole
        return self._lay_out(offered, metrics, area, top, height, limit, overflow=True)

    def _bar_reserve(
        self,
        metrics: QFontMetrics,
        area: QRect,
        index: QModelIndex | _PersistentIndex,
    ) -> int:
        """How much of the last line the progress bar keeps from the verbs (`T-163`).

        **The verbs are the half that can give, and `T-135` already built the mechanism.** A
        dropped verb is still reachable through `⋯` and through the context menu, so nothing is
        lost by dropping one sooner. A squeezed bar has no equivalent: there is no overflow menu
        for *progress*, and `T126-R2` already ruled that a row must not stop saying one true thing
        in order to say another.

        **What the bar needs depends on what it has to show** — a segmented bar for sixteen
        entries needs more than a single fraction does — so the figure comes from the same
        `MIN_BLOCK_WIDTH` the merge threshold does rather than from a second number.

        **The `⋯` outranks the reserve, and that is the one place the bar gives way.** On a line
        too narrow for both, a row that kept its bar and dropped the button would leave the
        pointer no route to its verbs at all. So the bar takes what is left under that, honestly
        below its minimum, rather than the row losing the only thing that can restore the rest.

        Measured off `area`, which is the row's whole text line, so this answer does not depend on
        what happened to fit — `_verb_rects` and `_paint_text` both ask it and must agree.

        **What the bar asks for is its *widest* rendering, never the one this width chose**
        (`T-168`). Asking `segment_blocks` here was the defect: the merge is a step, so the reserve
        fell 271 px to 135 px as the row crossed the threshold and handed the verbs 136 px back for
        being made *smaller*. A sixteen-entry playlist's `Remove` therefore vanished at 496 px,
        returned at 432 px and vanished again at 360 px — measured.

        Taking `segment_span(entries)` makes the space left for the verbs
        `max(0, area.width() - span - VERB_GAP)`, which is **continuous and non-decreasing** in the
        row's width: there is no width at which narrowing the window gives a verb back. Below the
        threshold the whole line goes to the bar and `⋯` is all that is left, which is the reported
        expectation.

        **The bar is not made narrower by this.** It is drawn into whatever the verbs leave, and
        `_paint_segments` still chooses its block count from `_bar_line` — so a merged bar spends
        the freed width on eight wider blocks instead of surrendering it, which is more of `T-164`
        rather than less.
        """
        # **A playlist entry keeps nothing, because it draws no bar** (`T-244`, `T244-R1`).
        # `_paint_text` returns at the child branch before it reaches the bar — row 9c's two lines
        # have no room for one — while this went on reading `PROGRESS_ROLE`, which a child answers
        # like any other row. The width it kept came straight out of the verbs' share.
        #
        # **A running entry is where it showed, and it is the state that can least afford it.** It
        # offers exactly one verb, `Cancel`, and it is the only child state carrying a fraction —
        # so restoring the phantom reserve drops that verb into the `⋯` menu at **every width from
        # 150 to 204 px**. The one control for stopping a download in progress, behind a menu, for
        # a bar that is not on the row. Gated by
        # `test_a_running_entry_keeps_its_cancel_on_the_row_at_a_narrow_width`.
        #
        # *(This comment claimed the branch changed no layout at any width and that no mutation was
        # claimed for it. Both were wrong, and `T244-R1` is the record: the sweep behind them paired
        # a **queued** row's three verbs with a fraction — a combination the model never produces,
        # and one where the overflow is needed anyway and hides the difference. The pairing that
        # matters, one verb beside a real fraction, was never tried. Measured from the composed
        # model now.)*
        if _depth(index) > 0:
            return 0
        room = self._bar_line(metrics, area, index)
        entries = len(_segments(index))
        if entries:
            keep = segment_span(entries)
        elif _fraction(index) is not None:
            keep = MIN_FRACTION_BAR
        else:
            return 0
        return min(keep, room)

    def _bar_line(
        self,
        metrics: QFontMetrics,
        area: QRect,
        index: QModelIndex | _PersistentIndex,
    ) -> int:
        """The most of the last line the bar can be given, and so what it decides its shape from.

        **One number for both, because two would let them disagree** (`T-163`, `T-167`). The
        rendering used to be chosen against the whole text line while the bar was only ever handed
        what remained under the `⋯`, so at a 631 px window the row decided on sixteen blocks and
        then drew them 15 px wide — the merge threshold reasoning about space the bar never had.

        Monotonic in the window's width, which is `T-167`'s requirement: everything subtracted here
        is fixed for a given row rather than a function of what fit on this paint.
        """
        room = max(area.width(), 0)
        if self._verbs_of(index):
            overflow = metrics.horizontalAdvance(MORE_LABEL) + 2 * VERB_PADDING
            # `-1` because `area.right()` is the last pixel rather than one past it, and the gap
            # because the bar stops `VERB_GAP` short of the leftmost button.
            room = max(room - overflow - VERB_GAP - 1, 0)
        return room

    def _lay_out(
        self,
        offered: Sequence[Verb],
        metrics: QFontMetrics,
        area: QRect,
        top: int,
        height: int,
        limit: int,
        *,
        overflow: bool,
    ) -> list[tuple[Verb | None, QRect]]:
        """Place as many verbs as fit right of `limit`, right to left, `⋯` first when asked."""
        placed: list[tuple[Verb | None, QRect]] = []
        right = area.right()
        wanted: tuple[Verb | None, ...] = (
            (None, *reversed(offered)) if overflow else tuple(reversed(offered))
        )
        for verb in wanted:
            label = MORE_LABEL if verb is None else LABELS[verb]
            width = metrics.horizontalAdvance(label) + 2 * VERB_PADDING
            left = right - width
            if left < limit:
                # **Silently dropped rather than drawn overlapping the message.** `NFR-006` gives
                # the extractor's message the full width above; a verb that will not fit is what
                # the overflow is for, and the overflow is placed first so it always survives.
                #
                # `limit` is the row's left edge plus whatever the progress bar keeps (`T-163`),
                # so a verb is now dropped for crowding the bar as well as for running off the row.
                break
            placed.append((verb, QRect(left, top, width, height)))
            right = left - VERB_GAP
        return placed

    def overflowing(self, row_id: str) -> tuple[Verb, ...]:
        """The verbs the row for `row_id` offers but had no room to draw.

        **What the last paint actually dropped, not a second opinion about what it would drop**
        (`T-135`). Recomputing the layout here would need this method to reproduce the row's width,
        its font and whether it carries a format control — three chances to disagree with the row
        the user is looking at, and a menu that disagrees with the row is the thing `_show_row_menu`
        already says would be worse than no menu.

        Reading a paint-time record is sound because the `⋯` cannot be clicked before it is drawn:
        every route into this method runs after the paint that filled it.
        """
        return self._dropped.get(row_id, ())

    def forget_dropped(self) -> None:
        """Discard the paint-time record (`T-135`).

        Clears the hovered verb too: it is keyed by row number, and a reset is exactly when a row
        number stops naming what it named.

        Called when the model resets, so a job that has left the queue cannot keep an entry here.
        The record is small and self-correcting — the next paint rewrites every visible row — but
        "self-correcting" is not "correct", and rows that scroll out of view are never repainted.
        """
        self._dropped.clear()
        self._hovered = None
        self._hovered_zone = None
        self._pressed_zone = None

    def _twisty_rect(self, option: QStyleOptionViewItem) -> QRect:
        """Where the disclosure is, for the paint and the click alike (`T-140`).

        One definition, for `_verb_rects`' reason: a control drawn in one place and hit-tested in
        another works where nobody clicks. Generous by design — the wedge is 9px and the target is
        the full indent, because a 9px click target is not one.
        """
        body = option.rect.adjusted(PADDING, PADDING, -PADDING, -PADDING)
        return QRect(body.left(), body.top(), TWISTY_WIDTH + PADDING, min(24, body.height()))

    def _paint_twisty(
        self, painter: QPainter, body: QRect, colour: QColor, *, opened: bool
    ) -> None:
        """The disclosure triangle on a group row (`T-140`).

        **Drawn as a filled wedge rather than a text glyph.** `T-133` is the record of what a
        style sheet does to a sub-control it was not told about, and a `▸` in a label is at the
        mercy of whichever font the platform resolves — `T-068` is the record of that. Three
        points cannot be un-drawn or substituted.
        """
        middle = body.top() + min(TWISTY_WIDTH, body.height()) // 2 + 2
        left = body.left() + 2
        size = 4
        if opened:
            points = (
                QPoint(left, middle - size // 2),
                QPoint(left + 2 * size, middle - size // 2),
                QPoint(left + size, middle + size),
            )
        else:
            points = (
                QPoint(left + 1, middle - size),
                QPoint(left + 1 + size, middle),
                QPoint(left + 1, middle + size),
            )
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour)
        painter.drawPolygon(points)
        painter.restore()

    def _paint_rail(self, painter: QPainter, rect: QRect, colour: QColor) -> None:
        """The line joining a group's entries to it (`T-140`).

        It is what makes an indented row read as *belonging* rather than as merely indented, which
        is the whole reason `UX-005` row 9 chose an opening row over sixteen loose ones.
        """
        rail = QColor(colour)
        rail.setAlpha(90)
        x = rect.left() + PADDING + TWISTY_WIDTH // 2
        painter.save()
        painter.setPen(rail)
        painter.drawLine(x, rect.top(), x, rect.bottom())
        painter.restore()

    def _paint_segments(
        self,
        painter: QPainter,
        area: QRect,
        states: Sequence[SegmentState],
        muted: QColor,
        palette: QPalette,
        *,
        line_width: int,
    ) -> None:
        """One block per entry, filled by what that entry has done (`UX-005` row 9b, `T-140`).

        **Not a percentage, and that is the ruling rather than a rendering choice.** The entries'
        byte totals arrive one at a time, so a fraction across them has a denominator that grows
        while it runs and a bar that goes *backwards*. It also gives a **failed** entry somewhere
        to be seen: under one continuous bar a playlist that quietly skipped a track looks exactly
        like one that got everything.

        **`line_width` is the row's own line, not `area`** (`T-167`). What the bar looks like used
        to be decided from `area`, which is the space left over *after* the verbs — and the verbs'
        width is not monotonic in the window's: at the moment one drops into `⋯` (`T-135`) the
        leftover grows. So dragging one edge steadily made the bar change, change back and change
        again. A rendering decided from leftover space inherits every discontinuity of everything
        else sharing the line. The line's own width moves one way only, so the same threshold is
        stable by construction, and the bar is still *drawn* into whatever `area` it was given.

        **Below the threshold the entries merge into `MERGED_BLOCKS`** (`UX-005` row 9b-i,
        `T-164`), each block taking the worst state it covers. The gap does not vary with it: the
        previous narrow rendering dropped the gap to zero, and sixteen touching blocks are one bar
        to the eye — indistinguishable from `T-155`, where blocks merged *by accident*. Row 9b-i's
        constraint is that a deliberate merge must not look like that defect returning, so what
        changes at the threshold is the block count and nothing else.
        """
        if not states or area.width() <= 0:
            return
        states = _merge(states, segment_blocks(len(states), line_width))
        span = (area.width() - SEGMENT_GAP * (len(states) - 1)) / len(states)
        if span < 1:
            return
        # **A finished entry is the brand** (`T-140`, corrected twice). Every segment was drawn in
        # `muted`, so sixteen completed downloads looked exactly like sixteen waiting ones — the
        # bar reported nothing while reporting something.
        #
        # **The first correction read `palette.highlight()`, and said in a comment that
        # `T130-R1` kept `primary` there deliberately. `T130-R1` says the opposite.** It scopes
        # `selection-background-color: {theme.selection}` to `QListView, QTreeView, QTableView`
        # precisely so a *row* gets the quiet tint instead of the brand fill — and Qt propagates a
        # style sheet's selection colours into those widgets' palettes. `theme.py` documents that
        # propagation as the point of the arrangement. So this delegate reads the one palette in
        # the application where `Highlight` is **not** the brand: measured on the built window,
        # the application palette answers `#1e5e47` and the list's answers `#ebf1ee`, a near-white
        # tint that against a white row is no fill at all. A completed playlist drew sixteen blank
        # blocks.
        #
        # **Colour is never the only signal** (`NFR-005`): the chip beside this says `16 of 16`
        # and the second line says `16 done`, in words. This reinforces them.
        #
        # **Hue, not opacity, once the ending matters** (`T-165`). Done and failed were a brand
        # green and the ink at alpha 170 — two solid dark fills, so a wholly cancelled playlist
        # drew a wholly *filled* bar and filled is the shape the eye reads as finished. Row 3.6
        # only ever asked that failed differ from *queued*, and those did differ, by opacity; the
        # pair a user actually confuses is finished against abandoned. The semantic colours come
        # from the theme rather than the palette because Qt has no role for "this one failed", and
        # a hardcoded hex would be right in one theme and wrong in the other.
        active = theme.applied()
        done = QColor(active.primary)
        running = QColor(done)
        running.setAlpha(140)
        failed = QColor(active.stop)
        cancelled = QColor(active.muted)
        waiting = QColor(muted)
        waiting.setAlpha(60)
        colours = {
            SegmentState.DONE: done,
            SegmentState.RUNNING: running,
            SegmentState.FAILED: failed,
            SegmentState.CANCELLED: cancelled,
            SegmentState.WAITING: waiting,
        }
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        # **Each block ends where the next begins** (`T155-fix`). Taking the left from a rounded
        # cumulative position and the width from a separately rounded span is two arithmetics for
        # one geometry, and wherever `round(span)` exceeded the real step a block ran into its
        # neighbour and the gap vanished. Measured for sixteen entries before the fix: 7 of 15 gaps
        # lost at 600 px, 6 at 617, 2 at 733, none at 800 — deterministic per width, which is why
        # it looked intermittent to somebody resizing a window.
        for position, state in enumerate(states):
            left = area.left() + round(position * (span + SEGMENT_GAP))
            right = area.left() + round((position + 1) * (span + SEGMENT_GAP)) - SEGMENT_GAP
            block = QRect(left, area.top(), max(right - left, 1), area.height())
            painter.setBrush(QColor(colours[state]))
            painter.drawRect(block)
        painter.restore()

    def _paint_verbs(
        self,
        painter: QPainter,
        area: QRect,
        body: QRect,
        option: QStyleOptionViewItem,
        index: QModelIndex | _PersistentIndex,
    ) -> int | None:
        """Draw the row's verbs and return the x the rest of the last line must stop at.

        **`None` when nothing was drawn**, and that is not a detail: a row with no verbs must
        leave the last line exactly as it was before they existed. Returning `area.right()`
        instead regressed `T118-R8` — the selector would have been narrowed by the format
        control's slot again, which is the specific defect that finding exists for, and the row
        without a control and the row with one would have drawn different text.

        **Through the real style, as `QStyleOptionButton`**, for the reason `_paint_control` gives:
        a control the user is expected to recognise has to be the platform's button rather than
        something that resembled one on the machine it was drawn on, and it themes itself.

        **Nothing is drawn disabled** (`UX-005` §5). A verb absent from the model's list is absent
        from the row; there is no greyed state, because a greyed *Retry* says the application
        considered retrying and declined.
        """
        rects = self._verb_rects(painter.fontMetrics(), area, body, index)
        # **Recorded here because here is where it is decided** (`T-135`). The `⋯` menu holds what
        # the row could not show, and this is the only place that knows what that was.
        row_id = index.data(JOB_ID_ROLE)
        if isinstance(row_id, str) and row_id:
            drawn = {verb for verb, _ in rects}
            self._dropped[row_id] = tuple(
                verb for verb in self._verbs_of(index) if verb not in drawn
            )
        if not rects:
            return None

        widget = cast("QWidget | None", option.widget)
        style = widget.style() if widget is not None else QApplication.style()
        for verb, rect in rects:
            button = QStyleOptionButton()
            button.rect = rect
            button.palette = option.palette
            button.text = MORE_LABEL if verb is None else LABELS[verb]
            button.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Raised
            # **The one signal that says this is a control and not a picture of one** (`T-134`).
            # `T118-R12` won the argument that a reserved slot with nothing painted in it is an
            # affordance only for someone who already knows it is there; a painted button that
            # never reacts to the pointer is that same defect one step later.
            if self._hovered == (index.row(), verb):
                button.state |= QStyle.StateFlag.State_MouseOver
            style.drawControl(QStyle.ControlElement.CE_PushButton, button, painter, widget)
        return min(rect.left() for _, rect in rects) - VERB_GAP

    def _is_being_edited(self, index: QModelIndex | _PersistentIndex) -> bool:
        """Whether the live editor is currently open on this row.

        Tracked here rather than asked of the view, because the delegate is what creates and
        destroys the editor and so is the only thing that cannot be wrong about it.
        """
        return self._editing_row == index.row()

    def _paint_control(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | _PersistentIndex,
    ) -> None:
        """Draw the row's **Download as** control, through the real style (`UX-004`, `T118-R12`).

        `QStyleOptionComboBox` and `CC_ComboBox` rather than a hand-drawn rectangle: a control the
        user is expected to recognise has to be the platform's combo box, not something that
        resembles one on the machine it was drawn on. It also themes itself, which a rectangle
        would have to be told how to do twice.

        **The empty label is a surface with no inherited state** (`T126-R4`). `PRESET_ROLE`
        answering `None` means two different things: on the staging list it means *follows the
        batch*, and on the queue it means *no built-in describes this request* — a custom selector
        (`REQ-009`). Drawing `INHERITED_TEXT` for both told a queue row it was the same as an "all"
        that does not exist. The row still says what it is: `QueueModel` answers `SELECTOR_ROLE`
        with the literal selector exactly when the control cannot name it.
        """
        # **Never blank while the row has a value to describe** (`T-157`). A group whose
        # members disagree answers `PRESET_ROLE` with `None`, and an empty combo reads as
        # *unset* or *broken* rather than as *they differ*. `PRESET_PLACEHOLDER_ROLE` is
        # what to say instead, and only the group answers it.
        chosen = index.data(PRESET_ROLE)
        placeholder = index.data(PRESET_PLACEHOLDER_ROLE)
        if isinstance(chosen, str):
            label = chosen
        elif isinstance(placeholder, str) and placeholder:
            label = placeholder
        else:
            # **The preset's name, not the relation** (`UX-004`, `T-284`, ruled 2026-08-28). A row
            # following the batch is downloading with something, and the control's job is to say
            # what. The relation is on the row's detail line — *"… — following the batch"* — where
            # it does not have to fit the label field left after the frame, the arrow and the
            # `⋮` zone — ~146 px at this geometry, and style-dependent (`T284-R4`).
            inherited = index.data(PRESET_INHERITED_ROLE)
            label = inherited if isinstance(inherited, str) and inherited else ""

        # **The combo stops where the `⋮` zone begins** (`T-203`, `UX-011` option *E*). The zone
        # is carved from the control's own rect rather than laid out beside it, so the row's
        # anatomy — text area, verbs, control slot — is unchanged by its existence; what the zone
        # takes, it takes from the combo's width, which is why `MENU_ZONE_WIDTH` is fixed.
        box = QStyleOptionComboBox()
        box.rect = self._combo_rect(option, index)
        box.palette = option.palette
        box.currentText = label
        box.state = QStyle.StateFlag.State_Enabled
        if option.state & QStyle.StateFlag.State_MouseOver:
            box.state |= QStyle.StateFlag.State_MouseOver

        widget = cast("QWidget | None", option.widget)
        style = widget.style() if widget is not None else QApplication.style()
        style.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, box, painter, widget)
        # The label is a separate element: `CC_ComboBox` draws the frame and the arrow, and
        # `CE_ComboBoxLabel` draws the text inside whatever room they left.
        #
        # **Inset to where the editor puts its own text** (`T-283`). The style being asked here is
        # the *list view's*, and `QStyleSheetStyle` resolves rules against the widget it is handed
        # — so the sheet's `QComboBox { padding }` matches nothing and the painted label came out
        # 5 px left of the editor Qt creates on click. `T118-R12` made the two agree about the
        # rectangle; this makes them agree about the text inside it.
        #
        # The frame width comes from the style and the padding from `theme`, so neither is a
        # second opinion: changing the sheet's padding moves this, and the regression measures
        # both routes rather than asserting a number.
        # **Elided, because the ruled shape does not always fit** (`T284-R2`, ruled 2026-08-30).
        # The 2026-08-28 ruling chose the preset's name partly because it was *"the only one of the
        # three that never elides"*, and measurement refuted that: two of the five built-in names
        # are wider than the field, including the default, *Best video up to 1080p (MP4)* at 164 px.
        #
        # **The field is style-dependent and no number here is universal** (`T284-R4`): ~146 px
        # offscreen with no widget bound, 148 px measured through the production dark sheet on a
        # real widget. Both overflow the same two names, which is why the ruling does not turn on
        # which. Nothing reads a constant — the width comes from `_label_field()` at paint time.
        #
        # The maintainer's answer was to keep the shape and the width and let it end in an ellipsis,
        # because the full value is on the row's detail line either way. Without this the style
        # clips mid-glyph instead.
        shifted = self._label_box(box, style, widget)
        shifted.currentText = option.fontMetrics.elidedText(
            box.currentText,
            Qt.TextElideMode.ElideRight,
            self._label_field(box, style, widget).width(),
        )
        style.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, shifted, painter, widget)

    def _paint_menu_zone(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | _PersistentIndex,
    ) -> None:
        """Draw the row's `⋮` — **the one part of the control slot that outlives the editor**.

        **Split out of `_paint_control` by `T-314`.** It used to be drawn at the tail of that
        method, which the paint pass suppresses while the live editor is open *"because it occupies
        the same rectangle"* — true of the combo and, since `T-203` carved the zone out of the
        slot, false of the zone. So opening the dropdown took the `⋮` with it, which the maintainer
        reported as the button disappearing. The combo is still suppressed under its editor; only
        this is not, and `_combo_rect` is what keeps the editor off it.
        """
        zone = self._menu_zone_of(option, index)
        # **The menu's painted door, drawn as a door** (`UX-011`, `UX-012`, `T-224`). Still an
        # affordance with no accessibility node — acceptable on the disclosure triangle's
        # precedent, because the same menu is reachable by right-click, the Menu key and
        # Shift+F10, which are real actions a screen reader announces.
        #
        # **A button, not punctuation.** The maintainer's report was that the glyph alone is *"not
        # a very pronounced button, people might even miss that they are there"*, and
        # discoverability is the zone's only job.
        #
        # **Drawn here rather than through `PE_PanelButtonTool`, and that was measured.** The
        # style primitive paints the same colours in every state under a view item's palette — a
        # probe found rest, hover, raised and sunken producing pixel-identical output — so a hover
        # delegated to it would be a state nobody could see. These three looks come from the
        # palette, so they follow both themes (`ARCHITECTURE.md` §8) and `T130-R1`'s contrast work.
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        palette = option.palette
        hovered = self._hovered_zone == index.row()
        pressed = self._pressed_zone == index.row()

        face = zone.adjusted(1, MENU_ZONE_INSET, -1, -MENU_ZONE_INSET)
        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            if pressed:
                painter.setBrush(palette.dark())
            elif hovered:
                painter.setBrush(palette.midlight())
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
            # **The border is what says "pressable", in every state** — so the affordance is not
            # carried by colour alone (`NFR-005`, `T-202`'s rule). Hover and press change the
            # *fill*; the outline is always there, which is what "bordered at rest" means.
            painter.setPen(palette.mid().color() if not pressed else palette.shadow().color())
            painter.drawRoundedRect(face, MENU_ZONE_RADIUS, MENU_ZONE_RADIUS)
        finally:
            painter.restore()

        painter.setPen(palette.highlightedText().color() if selected else palette.text().color())
        painter.drawText(zone, Qt.AlignmentFlag.AlignCenter, MENU_ZONE_GLYPH)

    def _paint_tile(
        self,
        painter: QPainter,
        body: QRect,
        index: QModelIndex | _PersistentIndex,
        *,
        size: tuple[int, int] = THUMBNAIL_SIZE,
    ) -> None:
        """The picture if there is one, the derived tile until then (`UX-003`).

        **Never an empty box.** A column of empty wells reads as a broken application, and it reads
        worse the more rows there are — which is the case this design exists for.
        """
        width, height = size
        tile = QRect(body.left(), body.top(), width, height)

        pixmap: QPixmap | None = None
        if self._thumbnails is not None:
            url = index.data(THUMBNAIL_URL_ROLE)
            pixmap = self._thumbnails.pixmap(url if isinstance(url, str) else None)

        if pixmap is not None and not pixmap.isNull():
            # **Fitted to the box, then centred in it** (`T-154`). This took the *pixmap's* size and
            # centred that on the tile, which overflows whenever the picture is bigger than the
            # slot. That never showed on a parent row, because `ThumbnailStore` caches at
            # `THUMBNAIL_SIZE` and the two agree — and it showed on every child row, whose
            # `CHILD_THUMBNAIL` slot is smaller, as a full-size picture drawn over its own title.
            #
            # The aspect ratio the old comment was reaching for is kept, by scaling rather than by
            # hoping: `KeepAspectRatio` fits the longer edge, so a square picture does not stretch
            # to 16:9 and a wide one no longer leaves the box.
            drawn = pixmap.size().scaled(tile.size(), Qt.AspectRatioMode.KeepAspectRatio)
            target = QRect(tile)
            target.setSize(drawn)
            target.moveCenter(tile.center())
            painter.drawPixmap(target, pixmap)
            return

        hue = index.data(HUE_ROLE)
        hue = hue if isinstance(hue, int) else 0
        painter.fillRect(tile, QColor.fromHsv(hue, 90, 110))
        painter.setPen(QColor.fromHsv(hue, 60, 190))
        painter.drawRect(tile.adjusted(0, 0, -1, -1))
        self._paint_placeholder_glyph(painter, tile, index, hue)

    def _paint_placeholder_glyph(
        self,
        painter: QPainter,
        tile: QRect,
        index: QModelIndex | _PersistentIndex,
        hue: int,
    ) -> None:
        """A faint mark over the hue block, so the absence reads as chosen (`T-217`).

        **The colour block on its own reads as a broken image**, which is the opposite of what the
        derived tile is for — `_paint_tile`'s *"never an empty box"* was solving the same problem
        one step earlier, and stopped short of saying what the box is standing in for.

        **Low opacity, over the block rather than instead of it.** The hue is what makes one row
        distinguishable from the next while a queue is still loading; a glyph that covered it would
        trade a working signal for a new one. `PLACEHOLDER_GLYPH_ALPHA` is measured against both
        grounds — see its comment for what "reads in both palettes" was checked to mean here.

        **Decorative, with no accessible name** (`T-217`, and `T-203`'s stance on the `⋮`). The row
        already says what it is in words: the headline, the detail line and the format selector are
        all in the accessibility tree, and `MediaKind` is visible there as the preset's name. A
        second announcement of *audio* would be noise on every row of a queue.
        """
        kind = index.data(MEDIA_KIND_ROLE)
        # `str`, not `MediaKind` — see `MEDIA_KIND_ROLE` for why, and for what narrowing on the
        # enum cost. Anything else, including `None`, leaves the plain block.
        if not isinstance(kind, str) or kind not in (MediaKind.AUDIO, MediaKind.VIDEO):
            return

        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            ink = QColor.fromHsv(hue, 40, 235)
            ink.setAlpha(PLACEHOLDER_GLYPH_ALPHA)
            side = max(8, int(tile.height() * PLACEHOLDER_GLYPH_SCALE))
            if kind == MediaKind.AUDIO:
                painter.setPen(ink)
                font = QFont(painter.font())
                # Sized off the tile rather than off the row's text, because a child row draws the
                # same mark in a smaller slot (`CHILD_THUMBNAIL`) and a fixed point size would
                # fill it.
                font.setPixelSize(side)
                painter.setFont(font)
                painter.drawText(tile, Qt.AlignmentFlag.AlignCenter, AUDIO_GLYPH)
            else:
                self._draw_film_frame(painter, tile, ink, side)
        finally:
            painter.restore()

    @staticmethod
    def _draw_film_frame(painter: QPainter, tile: QRect, ink: QColor, side: int) -> None:
        """A frame of film — an outline with sprocket holes down both edges (`T217-R1`).

        **Drawn rather than typed, and the reason is a platform assumption I would otherwise be
        making.** The task asks for a film frame; the first build shipped `▶`, a play triangle,
        which says *this will play* rather than *this is video* and was not what was scoped. The
        obvious replacement is `U+1F39E FILM FRAMES` — and `QFontMetrics.inFont` says it is **not**
        in the base font. It happens to render here through a fallback, on this machine, in this
        container. That is precisely the class of assumption `T146-R3`, `T199-R4` and `T-197` were
        each corrected for, and a tile that draws a blank box on a machine without the fallback is
        worse than the colour block it replaced.

        Two rows of holes and a frame is what reads as film at this size; a strip with more than
        two would turn to mush by the time a child row's slot has it.
        """
        height = side
        width = int(height * 1.15)
        frame = QRect(0, 0, width, height)
        frame.moveCenter(tile.center())

        painter.setPen(ink)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(frame)

        hole = max(1, height // 7)
        gap = max(1, (frame.height() - 3 * hole) // 4)
        painter.setBrush(ink)
        painter.setPen(Qt.PenStyle.NoPen)
        for row in range(3):
            top = frame.top() + gap + row * (hole + gap)
            painter.drawRect(QRect(frame.left() + hole, top, hole, hole))
            # `right()` is the last pixel *inside* the rect, so mirroring the left
            # hole's offset needs the `+ 1`. Without it the two columns sit a pixel
            # apart and the frame is not symmetric — which the shape regression sees.
            painter.drawRect(QRect(frame.right() - 2 * hole + 1, top, hole, hole))

    def _paint_text(
        self,
        painter: QPainter,
        area: QRect,
        body: QRect,
        index: QModelIndex | _PersistentIndex,
        primary: QColor,
        muted: QColor,
        verbs_left: int | None,
        palette: QPalette,
    ) -> None:
        if area.width() <= 0:
            return
        metrics = painter.fontMetrics()
        line = metrics.height()

        # **Whatever text lands on the last line yields its right-hand end to the verbs**
        # (`UX-005` §4, `T-244`). On an ordinary row the last line is the selector's and the bar's,
        # and both already give way — so this changes nothing there, which is deliberate: `T-166`
        # is the record of narrowing a line the verbs do *not* occupy, and `T118-R8` of narrowing
        # the one line that must not give.
        #
        # **A playlist entry is where it bites.** Row 9c leaves it two lines, so its last line is
        # the *detail* — and buttons drawn over an elided sentence is the collision this avoids
        # without spending the height row 9c bought. Which line that is comes from `_text_lines`,
        # so the text and the buttons cannot hold different opinions about it.
        lines = _text_lines(index)

        def room_on(row_line: int) -> int:
            if verbs_left is None or row_line != lines - 1:
                return area.width()
            return max(verbs_left - area.left(), 0)

        state = _text(index, STATE_ROLE)
        # **The chip's words are the model's, not this delegate's** (`T-130`, `T130-R3`). Drawn
        # first so the headline knows how much width is left, and right-aligned on the title's own
        # line, which is where the mockup puts it and where the eye already is. See
        # `STATE_CHIP_ROLE` for why deriving the text here could not be made correct.
        chip_text = index.data(STATE_CHIP_ROLE)
        chipped = isinstance(chip_text, str) and bool(chip_text)
        headline_width = area.width()
        if chipped:
            chip_width = metrics.horizontalAdvance(chip_text) + 2 * CHIP_PADDING
            chip = QRect(
                max(area.right() - chip_width, area.left()),
                area.top() + (line - metrics.height()) // 2,
                min(chip_width, area.width()),
                metrics.height(),
            )
            painter.setPen(muted)
            painter.drawRoundedRect(chip.adjusted(0, 0, -1, -1), CHIP_RADIUS, CHIP_RADIUS)
            painter.drawText(chip, int(Qt.AlignmentFlag.AlignCenter), chip_text)
            headline_width = max(chip.left() - GAP - area.left(), 0)

        headline = _text(index, HEADLINE_ROLE)
        painter.setPen(primary)
        painter.drawText(
            QRect(area.left(), area.top(), headline_width, line),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            metrics.elidedText(headline, Qt.TextElideMode.ElideRight, headline_width),
        )

        detail = _text(index, DETAIL_ROLE)
        # **Dropped from here only when the chip already says exactly it** (`T130-R3`).
        #
        # The chip used to take the state off this line unconditionally, on the reasoning that the
        # same word twice on one row is waste and `NFR-006` wants this width for the extractor's
        # message. That reasoning holds for `Queued`, where the chip and this line would say the
        # one word — and it silently stopped holding the moment the chip started reading `62%`,
        # because then the chip and the stage are *different facts* and dropping the state deleted
        # `Downloading video` and `Post-processing` from the row altogether. So the test is the one
        # the original reasoning actually meant: identical text, not merely both present.
        parts = (detail,) if chipped and state == chip_text else (detail, state)
        second = " — ".join(part for part in parts if part)
        painter.setPen(muted)
        detail_room = room_on(1)
        painter.drawText(
            QRect(area.left(), area.top() + line, detail_room, line),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            metrics.elidedText(second, Qt.TextElideMode.ElideRight, detail_room),
        )

        # **What the user can do about it, on a line of its own** (`ACTION_ROLE`, `T201-R3`, ruled
        # 2026-08-14). `NFR-006`'s third fact, and the row is the only surface there is for it —
        # `UX-005` §2 removed the detail pane, and the widget that composed all three was reachable
        # from nowhere.
        #
        # **Below the reason rather than beside it**, which is the whole of the ruling. Appended to
        # the line above, the two would have shared one elision and the extractor's own message is
        # what would have been cut: measured at 1180 px, `--ffmpeg-location` became `--ff…`, so the
        # remedy yt-dlp itself supplied was the price of stating the remedy this table supplies.
        # On its own line the message above keeps the full width it had before this existed.
        #
        # Elided rather than wrapped: a second line for the action would be the same trade one step
        # further on, and these sentences are written to fit. Drawn in the same muted ink as the
        # reason, so nothing here is a colour-only signal (`NFR-005`, `T-202`).
        action = _text(index, ACTION_ROLE)
        action_lines = _action_lines(index)
        if action:
            action_room = room_on(2)
            painter.drawText(
                QRect(area.left(), area.top() + 2 * line, action_room, line),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                metrics.elidedText(action, Qt.TextElideMode.ElideRight, action_room),
            )

        # **A child row draws two lines, not four** (`UX-005` row 9c, `T-140` corrected).
        # `sizeHint` was shortened for an entry and the painter was not, so the selector and the
        # bar were drawn into space the row does not have and were **clipped** — the maintainer saw
        # a half line of text under every entry. An entry inherits its group's format, so the third
        # line has nothing to say; not drawing it is the promise, and sizing for it was only half.
        if _depth(index) > 0:
            # **A child speaks only when it differs from its group** (`UX-005`, amended
            # 2026-08-05; `T-157`). Row 9c gives an entry no format line because it inherits the
            # group's — and retargeting a part-done playlist breaks that premise, since a finished
            # track keeps the old format while the queued ones take the new. The model answers an
            # empty string when they agree, so the economy is kept for every uniform playlist and
            # a line is spent only where there is something to say.
            own = _text(index, SELECTOR_ROLE)
            if own:
                own_room = room_on(2 + action_lines)
                painter.drawText(
                    QRect(area.left(), area.top() + (2 + action_lines) * line, own_room, line),
                    int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
                    metrics.elidedText(own, Qt.TextElideMode.ElideRight, own_room),
                )
            return

        selector = _text(index, SELECTOR_ROLE)
        selector_lines = 0
        if selector:
            # **Not elided, and not narrowed by the control's slot** (`T118-R8`, `REQ-009`).
            #
            # This line was passed through `ElideRight` at the width left over beside the editor
            # slot — 382 px at the tests' own render width — against a built-in selector that
            # measures up to 962 px. The literal selector, which is the entire point of the line,
            # was cut off every time; the tests asserted the model's string and so never saw it.
            #
            # So it wraps instead of eliding, and it runs the **full** body width: the control sits
            # beside the first two lines, and nothing needs the third line's right-hand end.
            # `SELECTOR_LINES` of room, which holds every built-in at the default font and is
            # explicitly *not* a promise at larger ones — see that constant, and `T118-R15`.
            # **The verbs own the last line, so the selector gives up that line** (`UX-005` §4).
            # Without this the selector wraps across lines 2 and 3 and the buttons are drawn over
            # its second line. *(This said "which is the history row's shape exactly, since the
            # saved path is long" — the history row is gone, `T-169`/`T-170`. The geometry it
            # described is the live one: any row carrying verbs and a long selector. `T-186`.)*
            # A row with no verbs keeps both lines, which is the add dialog's case and the one
            # `T118-R15` sized `SELECTOR_LINES` for.
            selector_lines = max(SELECTOR_LINES - (0 if verbs_left is None else 1), 1)
            # **The line it keeps is at the full width, whatever the verbs are doing** (`T-166`).
            # This used to stop at `verbs_left` as well, and the verbs are on the line *below*: the
            # height above already gave them their line, so narrowing this one as well spent the
            # same width twice. As the window narrowed the buttons advanced leftward across a line
            # they do not occupy, and `Download as: Best video available` was drawn as `Download`.
            #
            # **The format line is the half that cannot give** (`T118-R8`): a truncated selector is
            # one the user can neither read nor copy, and there is no overflow menu for a sentence.
            # The verbs have one, and `T-163` is where they give way.
            painter.drawText(
                QRect(
                    area.left(),
                    area.top() + (2 + action_lines) * line,
                    max(body.right() - area.left(), 0),
                    selector_lines * line,
                ),
                SELECTOR_FLAGS,
                selector,
            )

        # **A group's bar is its entries, not a fraction of them** (`UX-005` row 9b, `T-140`).
        # Tested before `PROGRESS_ROLE` because a group answers no fraction at all — there is no
        # honest one to answer, which is the finding row 9b records.
        segments = _segments(index)
        fraction = _fraction(index)
        if not segments and fraction is None:
            return
        # **The bar goes under the selector rather than instead of it** (`T126-R2`). This used to
        # return outright when a selector was present, on the reading that no model answers both
        # roles — true until `T126-R2` made a started download say what format it is running as,
        # which is `UX-005` §6's "plain format text once a download starts". A row that dropped its
        # progress bar the moment it acquired that text would trade one half of `UX-005` §3's
        # anatomy for the other. `sizeHint` already reserves `TEXT_LINES`, and the guards below
        # drop the bar rather than draw it outside the row when a large font leaves no room.
        #
        # **Stops where the verbs start** (`UX-005` §4). The bar and the buttons share the last
        # line; a bar drawn the full width would run underneath them, which is the same defect as
        # a control drawn where nobody clicks, seen from the paint side.
        bar = QRect(
            area.left(),
            area.top() + (2 + action_lines + selector_lines) * line + 2,
            max((area.right() if verbs_left is None else verbs_left) - area.left(), 0),
            BAR_HEIGHT,
        )
        if bar.width() <= 0:
            return
        if bar.bottom() > area.bottom():
            return
        if segments:
            # **The line's width, not the bar's** (`T-167`). `_bar_line` differs from the row's own
            # width by the padding, the indent, the tile, the control's slot and the overflow
            # button — all fixed for a given row, so it moves one way as the user drags. `bar` is
            # what the verbs left of it, and that is exactly the input whose reversals made the
            # bar change shape twice on one drag. The same call decides the reserve `_verb_rects`
            # laid the buttons out against, so the two cannot disagree about the block count.
            self._paint_segments(
                painter,
                bar,
                segments,
                muted,
                palette,
                line_width=self._bar_line(metrics, area, index),
            )
        elif fraction is not None:
            track = QColor(muted)
            track.setAlpha(60)
            painter.fillRect(bar, track)
            done = QRect(bar)
            done.setWidth(int(bar.width() * min(max(fraction, 0.0), 1.0)))
            painter.fillRect(done, muted)

    # --- the one editor -------------------------------------------------------------------

    def _editable(self, index: QModelIndex | _PersistentIndex) -> bool:
        choices = index.data(PRESET_CHOICES_ROLE)
        return bool(choices)

    def _verb_area(
        self, option: QStyleOptionViewItem, index: QModelIndex | _PersistentIndex
    ) -> tuple[QRect, QRect]:
        """The row's body and the area its text and verbs are laid out in — one definition.

        Extracted at `T-134`, when hover became the third thing that had to agree with the paint
        and the click about where the buttons are. Two copies of this arithmetic were already one
        more than `_verb_rects`' own rule allows, and at `T-160` `paint` stopped keeping a fourth.

        **The slot taken out is the control's real width, not `EDITOR_WIDTH`** (`T-160`). The
        control narrows on a row that cannot hold all of it, and reserving the full width there
        would leave a gap the row has no way to spend.
        """
        body, tile = self._body_of(option, index)
        text_left = body.left() + tile[0] + GAP
        text_area = QRect(text_left, body.top(), max(body.right() - text_left, 0), body.height())
        if self._editable(index):
            control = self._control_of(option, index)
            text_area.setWidth(max(text_area.width() - control.width() - GAP, 0))
        return body, text_area

    def watch_hover(self, view: QAbstractItemView) -> None:
        """Let this delegate see the pointer move over `view` (`T-134`).

        **Two things, and neither is a default.** A viewport's mouse tracking is off, so Qt
        delivers `MouseMove` only while a button is held — measured, not assumed — and without the
        filter nothing tells the delegate the pointer left the widget, so the last hovered button
        would stay lit over an empty list.
        """
        viewport = view.viewport()
        viewport.setMouseTracking(True)
        viewport.installEventFilter(self)

    def eventFilter(self, watched: Any, event: Any) -> bool:
        """Drop the hover when the pointer leaves the viewport (`T-134`)."""
        if isinstance(event, QEvent) and event.type() == QEvent.Type.Leave:
            self.forget_hover()
        return bool(super().eventFilter(watched, event))

    def forget_hover(self) -> None:
        """Clear the hovered verb and zone, repainting if that changed anything (`T-134`)."""
        if self._hovered is None and self._hovered_zone is None and self._pressed_zone is None:
            return
        self._hovered = None
        self._hovered_zone = None
        self._pressed_zone = None
        self._repaint()

    def _hover_at(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex | _PersistentIndex,
        where: QPoint,
    ) -> None:
        """Record what the pointer is over, repainting only when the answer changes."""
        body, text_area = self._verb_area(option, index)
        found: tuple[int, Verb | None] | None = None
        for verb, rect in self._verb_rects(QFontMetrics(option.font), text_area, body, index):
            if rect.contains(where):
                found = (index.row(), verb)
                break
        # The `⋮` zone, resolved through `_menu_zone_of` — the same one definition the paint and
        # the hit test read, so a hover cannot light a rectangle the click does not answer
        # (`T-203`'s seam, `T-224`).
        zone_row = index.row() if self._menu_zone_of(option, index).contains(where) else None
        if found == self._hovered and zone_row == self._hovered_zone:
            # **Moving within one button repaints nothing.** A repaint per mouse move over a list
            # of rows is the cost `T118-R10` spent a finding on in the other direction.
            return
        self._hovered = found
        self._hovered_zone = zone_row
        self._repaint()

    def _repaint(self) -> None:
        view = cast("QAbstractItemView | None", self.parent())
        if view is None:
            return
        view.viewport().update()

    def editorEvent(
        self,
        event: Any,
        model: QAbstractItemModel,
        option: QStyleOptionViewItem,
        index: QModelIndex | _PersistentIndex,
    ) -> bool:
        """Open the row's editor when the user clicks the control that is drawn on it.

        **The direct interaction, which is what makes the painted affordance a control** rather
        than a picture of one (`T118-R12`). `SelectedClicked` alone required the row to be selected
        first, so a click on an unselected row's control selected the row and did nothing visible —
        the user had to click the same place twice and had no way to know that.

        Returns `False` for everything else, so the view keeps its ordinary selection behaviour.
        """
        if not isinstance(event, QMouseEvent):
            return False
        if event.type() == QEvent.Type.MouseMove:
            # **Hover is tracked here because here is where the rects are** (`T-134`). Requires
            # `watch_hover` to have turned the viewport's mouse tracking on: without it Qt sends
            # `MouseMove` only while a button is held, so the highlight would appear on drag.
            self._hover_at(option, index, event.position().toPoint())
            return False
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        if event.type() == QEvent.Type.MouseButtonPress:
            # **The press is where the sunken face begins, and it has to be handled here or it is
            # not a state at all** (`T224-R1`). The first build set `_pressed_zone` on *release*,
            # asked for an asynchronous `viewport().update()`, and cleared it on the next line —
            # so the value was gone before any paint could run, and the sunken look was
            # unreachable. A probe confirmed `_pressed_zone` was `None` both after release and
            # inside the menu signal's own handler.
            #
            # Consumed (`True`) only for the zone, so a press anywhere else keeps the view's
            # ordinary selection behaviour. The zone is a button; a button that selects the row
            # underneath it on the way down is two controls in one place.
            if self._editable(index) and self._menu_zone_of(option, index).contains(
                event.position().toPoint()
            ):
                self._pressed_zone = index.row()
                self._repaint()
                return True
            return False
        if event.type() != QEvent.Type.MouseButtonRelease:
            return False
        # **Released, wherever it landed** (`T224-R1`). A press inside the zone and a release
        # outside it must not leave the face drawn sunken — that is the "button stuck down" the
        # first build's comment was worried about, arrived at from the other direction.
        if self._pressed_zone is not None:
            self._pressed_zone = None
            self._repaint()
        body, text_area = self._verb_area(option, index)
        where = event.position().toPoint()

        # **The disclosure is tested first**, because it sits left of everything else and a click
        # that reached the row's selection instead would open nothing and look broken.
        if isinstance(index.data(EXPANDED_ROLE), bool) and self._twisty_rect(option).contains(
            where
        ):
            row_id = index.data(JOB_ID_ROLE)
            if isinstance(row_id, str) and row_id:
                self.disclosure_toggled.emit(row_id)
                return True
            return False

        # **The verbs are tested first**, because they sit inside the text area and the control
        # sits beside it: an ambiguity would mean one of them is drawn where the other is clicked.
        # Tested from the same `_verb_rects` the paint used, so the two cannot disagree.
        for verb, rect in self._verb_rects(QFontMetrics(option.font), text_area, body, index):
            if rect.contains(where):
                job_id = index.data(JOB_ID_ROLE)
                if not isinstance(job_id, str) or not job_id:
                    # A row that offers a verb and cannot say which job it is about would send the
                    # action to whatever the receiver guessed. Refuse rather than guess.
                    return False
                self.verb_triggered.emit(job_id, verb)
                return True

        if not self._editable(index):
            return False
        # **The `⋮` zone opens the row's menu; the rest of the control still opens the combo**
        # (`T-203`, `UX-011` option *E*). Tested before the edit branch because the zone is inside
        # the control's rect — carved from it, in `_menu_zone_of` — so the order here is what
        # makes the two targets two, and the geometry regression asserts both sides of the line.
        if self._menu_zone_of(option, index).contains(where):
            # The sunken face was cleared above, before the menu opens — the menu takes the
            # pointer, so a zone left drawn pressed would stay that way behind it until the next
            # mouse move (`T-224`).
            self.menu_requested.emit(where)
            return True
        if not self._control_of(option, index).contains(where):
            return False
        view = cast("QAbstractItemView | None", self.parent())
        if view is None:
            return False
        view.setCurrentIndex(index)
        view.edit(index)
        return True

    def createEditor(
        self,
        parent: QWidget,
        option: QStyleOptionViewItem,
        index: QModelIndex | _PersistentIndex,
    ) -> QWidget:
        """**One** combo box, for the row currently being edited (`T118-R10`).

        Qt creates this when a row enters edit mode and destroys it when the row leaves, so the
        cost is one control regardless of how many rows exist. The design this replaces built one
        per row up front, which is the whole of the 0.722 s.

        **The inherited entry is the model's to offer** (`T126-R4`). It used to be prepended
        unconditionally, which is correct on the staging list — `UX-004` gives a paste one format
        and a row may defer to it — and false on the queue, where a job holds only its own durable
        request and the batch it arrived with is neither stored nor reachable. So the queue drew a
        first entry that `QueueModel.setData` then refused, naming a group that does not exist:
        a control which silently does nothing, which is what `UX-005` §5 forbids.

        The accessible description follows the same fact, rather than describing a paste to
        somebody looking at a queue.
        """
        self._editing_row = index.row()
        job_id = index.data(JOB_ID_ROLE)
        self._editing_job_id = job_id if isinstance(job_id, str) and job_id else None
        inheritable = bool(index.data(PRESET_INHERITABLE_ROLE))
        choice = QComboBox(parent)
        self._editor = choice
        choice.setObjectName(ROW_PRESET_NAME)
        choice.setAccessibleName("Download format for this URL")
        choice.setAccessibleDescription(
            "Choose a format for this URL alone. The first entry follows the format chosen for "
            "the whole paste."
            if inheritable
            else "Choose the format this download will use."
        )
        if inheritable:
            # **The same value the closed control showed, plus the relation** (`T-284`). Falls back
            # to the relation alone only where the surface says a row may follow and then cannot
            # name what — which no model does today, and which would otherwise put a bare suffix in
            # the list.
            inherited = index.data(PRESET_INHERITED_ROLE)
            choice.addItem(
                inherited_entry_text(inherited)
                if isinstance(inherited, str) and inherited
                else INHERITED_SUFFIX.strip(" —"),
                None,
            )
        offered = [str(name) for name in index.data(PRESET_CHOICES_ROLE) or ()]
        for name in offered:
            choice.addItem(name, name)
        # **The row's own format, when no built-in describes it** (`REQ-009`, `T-108`). A row that
        # chose `137+140` from the table holds a preset that is not in the catalogue, so
        # `setEditorData`'s `findData` would miss and the control would open showing *nothing
        # selected* for a row that has very much chosen something. Added rather than left to the
        # `-1` fallback, which is the honest rendering on the queue — where the durable request may
        # be anything — and simply wrong here, where the dialog knows exactly what this row picked.
        current = index.data(PRESET_ROLE)
        if isinstance(current, str) and current and current not in offered:
            choice.insertItem(0, current, current)
        # **Presets, full stop** (`T-203`, `UX-011` option *E*). The three per-row verbs lived
        # here as entries that opened windows and put the selection back — *"looks like a value
        # picker while containing commands"*, the complaint that opened the task. They are now
        # entries in the row's own menu, behind the `⋮` zone and the context-menu routes;
        # `Manage presets…` went to the footer with `UX-009`. What remains is what the control
        # says it is: the preset this row downloads as.
        # `MANAGE_PRESETS_*` is deliberately absent: `UX-009` moved it to the dialog's footer,
        # because it edits the shared library and does the same thing from every row.
        return choice

    def destroyEditor(self, editor: QWidget, index: QModelIndex | _PersistentIndex) -> None:
        """Forget the open row. Every close route reaches here, which is why it is the one hook.

        **By identity, never by row number** (`T-211`, and it is `T118-R14`'s rule at teardown).
        This compared `index.row()` to the remembered row — but Qt destroys editors *during* a
        reset, after the rows have already shifted, so the row it names here is precisely the
        number that cannot be trusted. On a mismatch the guard skipped, `_editor` kept pointing at
        a widget whose C++ half was being deleted, and the next `commit_and_close_editor` walked
        into it: two *"commitData called with an editor that does not belong to this view"*
        warnings, then `RuntimeError: Internal C++ object (QComboBox) already deleted` — a crash
        the maintainer hit live. The editor being destroyed *is* the thing to forget; which row it
        was billed to is irrelevant.
        """
        if editor is self._editor:
            self._editing_row = None
            self._editor = None
            self._editing_job_id = None
        super().destroyEditor(editor, index)

    @property
    def editing_job_id(self) -> str | None:
        """Which job the open editor belongs to, or `None` if none is open (`T126-R1`).

        Read **before** `commit_and_close_editor`, by a surface that means to reopen the editor on
        the same job once the model has been rebuilt. By id and not by row: the whole reason the
        commit has to happen first is that a structural reset can move the row, and a restore that
        used the old number would reopen the editor on whatever job now occupies it.
        """
        return self._editing_job_id

    def commit_and_close_editor(self) -> bool:
        """Commit the open editor and close it. `True` if there was one (`T118-R14`).

        **Called before a model reset, never after.** A reset invalidates the editor's model index,
        after which Qt disowns the widget: `commitData` then reports *"called with an editor that
        does not belong to this view"*, `setData` is never reached, and the user's chosen format is
        discarded silently while the orphaned combo box stays on screen. The window for that is not
        teardown — it is any sibling row finishing its probe while someone is choosing a format.

        **The queue resets on remove, reorder and clear, so it needs this too** (`T126-R1`). The
        add dialog was given the lifecycle and the queue was given the same delegate without it,
        so choosing MP3 for a row and then reordering the queue discarded the choice in silence and
        left the download running as whatever it was before. `QueueView` now calls this from
        `modelAboutToBeReset`, which is emitted while the model still holds the rows the editor's
        index was resolved against.
        """
        view = cast("QAbstractItemView | None", self.parent())
        editor = self._editor
        if view is None or editor is None:
            return False
        self._editor = None
        self._editing_row = None
        self._editing_job_id = None
        view.commitData(editor)
        view.closeEditor(editor, QAbstractItemDelegate.EndEditHint.NoHint)
        return True

    def setEditorData(self, editor: QWidget, index: QModelIndex | _PersistentIndex) -> None:
        """Show what the row's request already is — **or nothing** (`T126-R4`).

        `max(wanted, 0)` was the old fallback, and dropping the inherited entry turned it into a
        lie: a queue row whose durable request is a custom selector (`REQ-009`) answers `None` for
        `PRESET_ROLE`, `findData` misses, and index `0` is then the *first built-in* — so a row
        downloading `bestvideo[height<=720]+bestaudio` would have opened its control reading
        "Best video available", and closing it unchanged would have said so to the manager.

        `-1` instead: the control shows no selection, which is the honest rendering of *"no
        built-in describes this"*, and `QueueModel` puts the literal selector on the row's own line
        for exactly that case.

        *(This continued: "A miss on the staging list cannot happen — its `None` is the inherited
        entry, which is present there." **That was the claim `T313-R3` disproved**, and the
        sentence had it backwards: the inherited entry being present is precisely what makes a miss
        dangerous there, because `-1` then commits as a deliberate choice rather than as nothing.
        A staging miss became reachable when `T-313` gave the role a value that varies; the body
        below now supplies the entry instead of relying on it never being absent.)*
        """
        if not isinstance(editor, QComboBox):
            return
        # **The inherited entry is rebuilt here, not only at `createEditor`** (`T284-R3`). The batch
        # preset can change while this editor is open — `StagingModel.refresh()` deliberately keeps
        # it alive across a value-only `dataChanged` — and an entry built once then names a preset
        # the row would no longer follow. Same shape as the label it mirrors: read the role now.
        inherited = index.data(PRESET_INHERITED_ROLE)
        entry = editor.findData(None)
        if entry != -1 and isinstance(inherited, str) and inherited:
            editor.setItemText(entry, inherited_entry_text(inherited))
        current = index.data(PRESET_ROLE)
        wanted = current if isinstance(current, str) else None
        position = editor.findData(wanted)
        if position == -1 and wanted is not None and editor.findData(None) != -1:
            # **A row's own value that this editor has no entry for gets one, here** (`T313-R3`).
            # `createEditor` adds it once; the role can change while the editor stays open, and
            # `StagingModel.refresh()` deliberately keeps it alive across a value-only
            # `dataChanged` — the same window `T284-R3` rebuilds the inherited entry in, one entry
            # over.
            #
            # **Without this the miss is not neutral, it is a lie.** `setCurrentIndex(-1)` leaves
            # `currentData()` answering `None`, which on this list is the inherited entry — so the
            # editor's next untouched commit arrives as *the user chose "follow the batch"* and
            # discards a hand-picked format nobody touched. That is the defect the reviewer
            # reproduced with a wheel event, and it is why the guard is on the **presence of an
            # inherited entry**: a list that has one is a list where `-1` is indistinguishable from
            # a deliberate choice. The queue has no such entry, so `-1` stays honest there and its
            # `T126-R2` rendering below is untouched.
            editor.insertItem(0, wanted, wanted)
            position = 0
        editor.setCurrentIndex(position)

    def setModelData(
        self,
        editor: QWidget,
        model: QAbstractItemModel,
        index: QModelIndex | _PersistentIndex,
    ) -> None:
        if not isinstance(editor, QComboBox):
            return
        model.setData(index, editor.currentData(), PRESET_ROLE)

    def updateEditorGeometry(
        self,
        editor: QWidget,
        option: QStyleOptionViewItem,
        index: QModelIndex | _PersistentIndex,
    ) -> None:
        """Put the editor in the slot `paint` already reserved for it, on the row it belongs to.

        **Only this delegate's own editor**, guarded the way `setEditorData` and `setModelData`
        beside it already guard — and that omission was `T-297` (`T-296` too, see below). Qt keeps
        `setIndexWidget` widgets in **the same map as item editors**, so every `updateGeometries()`
        pass hands this method the open row's *panel* and this method sized it as if it were the
        row's format combo: `_control_of` returns the small control slot, so a 354 px panel was set
        to **26 px**. A resize calls `updateGeometries()` per step, so the panel collapsed and was
        restored once per step — 107 collapses in 110 steps — and the view painted the row inside
        each gap. `RowDelegate.paint` draws the thumbnail on every row it is given because an open
        one is supposed to be covered by its panel, so what the user saw was the thumbnail cutting
        in and out for the length of the drag. Measured at
        `docs/project/evidence/2026-09-01-T297-panel-collapses-during-resize.md`.

        **`super()` for anything else, rather than leaving it alone**: `QStyledItemDelegate` sizes
        an editor to `option.rect`, which for an index widget spanning the row is exactly right —
        so the panel now gets its correct geometry from the same pass that used to shrink it.

        **This is also what `T-296` was working around.** That task reordered `_mount_panel` so
        `scrollTo` — which calls `updateGeometries()` — could not undo the geometry `setGeometry`
        had just set. The reorder is still correct and still tested, but the reason the scroll
        destroyed the geometry was this method, one layer down.
        """
        if not isinstance(editor, QComboBox):
            super().updateEditorGeometry(editor, option, index)
            return
        # **The same rectangle the affordance was painted in** (`T118-R12`), which since `T-314`
        # means `_combo_rect` rather than the whole control slot — the `⋮` zone is carved out of
        # both sides now, so the control neither moves nor covers the zone when it is clicked.
        editor.setGeometry(self._combo_rect(option, index))


def _text(index: QModelIndex | _PersistentIndex, role: int) -> str:
    """One role as a string. A model that does not answer a role contributes nothing to the row."""
    value: Any = index.data(role)
    return value if isinstance(value, str) else ""
