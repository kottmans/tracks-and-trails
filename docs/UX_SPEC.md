# UX_SPEC.md — Tracks & Trails

**Purpose:** What each surface shows, what it offers, and how a keyboard reaches it.
**Authority:** Canonical for the **built** surfaces below, which it absorbs from the `UX-` entries at
`DOC-002`'s trigger. `UX-007` ruled all twenty-five of the original `[P]` clauses on 2026-08-07.
**None is open.** `P-29` — §6's scroll region — was **ratified by the maintainer on 2026-08-13**,
as built. *(It had been demoted from `[D]` by review on 2026-08-11 and
listed in §10.
**Owner:** Planner
**Maintainer:** Sean Kottman
**Status:** Active — created 2026-08-06 for `T-105`, at the start of Phase 3
**Last updated:** 2026-08-11 — `T222-R2` demoted §6's scroll-region clause from `[D]` to `[P]`
and opened it as `P-29`; the clause is built ahead of ratification on the reviewer's instruction.
Before it, 2026-08-09: `UX-010` amended §2.2's group chip: a queue group's chip is
done-of-total progress, and the History count rule stays History's. Before it, 2026-08-07: `UX-007`
ruled every open `[P]` clause; `UX-006` (the queue is stopped until started) and `ARC-010` (option
coverage) amended §2, §2.1 and §6
**Update when:** A surface changes, a `UX-` entry is accepted or amended, or a §10 question is ruled on.
**Does not contain:** Why a decision was made (`docs/project/DECISIONS.md`), what must be tested
(`docs/project/TESTING.md`), the visual palette (`ARCHITECTURE.md` §8), or Phase 4's settings dialog
(`REQ-023`).

---

## 1 · How to read this, and which document wins

`DOC-002` deferred this file until *"Phase 3 begins"*. That trigger has fired, and two accepted
entries name this file as their destination: `UX-004` says `T-105` *"should absorb this anatomy when
it is written"*, and `UX-005` says *"`T-105` writes `docs/UX_SPEC.md` from this entry, and this
entry is the authority until it does."*

**So the authority moves here for what is built, and the `UX-` entries keep the reasoning.** That
split is deliberate: this project's recurring defect is two documents describing one thing and
drifting, and the fix is not to copy less but to say plainly which is which.

- **This file states what a surface *is*.** A disagreement between this file and an implementation
  is a defect in one of them.
- **`docs/project/DECISIONS.md` states why, and what was rejected.** A `UX-` entry accepted *after* this file
  is written amends it, and this file is then updated — the entry does not become a second spec.

### Every clause is marked, and the marks are not decoration

Phase 3's surfaces do not exist yet, so most of §4–§9 is being written before anything is built.
That is the point of writing it — and it is also how an implementer's preference becomes project
truth if nobody separates the two. `T145-R1` and `T144-R1` are what that costs: two decisions
recorded as maintainer rulings that no maintainer had made.

| Mark | Meaning |
|---|---|
| **[T]** *Transcribed* | Restated from an accepted decision or a requirement. This file may be wrong about it; the entry rules. |
| **[D]** *Derived* | Follows from an accepted rule applied to a new surface, taking no product choice of its own. The derivation is shown so it can be disputed. |
| **[P]** *Proposed* | **A product choice nobody has made.** Written so it can be ruled on, not so it can be built. Every one is collected in §10, and **no task may build a [P] clause until it is ratified.** **None is open.** `P-29` — `T-222`'s scroll-region clause in §6 — was ratified as built on 2026-08-13; `UX-007` ratified all twenty-five of the original set on 2026-08-07. |

---

## 2 · The window, as built

**[T]** `UX-005`, **amended 2026-08-06** (`T-169`). One list, no detail pane, every verb on the row.

> **The History tab is gone, and so is the tab widget.** `REQ-020` is **withdrawn**: the application
> keeps no record of what has been downloaded, so the second tab has no contents rather than fewer
> of them — and a tab strip holding one tab offers a choice the user does not have. Everything below
> that describes **a row** still stands; the Queue still has rows. The struck items are kept
> visible rather than deleted, because this section is what a reader checks the window against.

1. ~~**`Queue` and `History` are tabs**, each showing a count.~~ **The window is the Queue**
   (2026-08-06). No tab bar, no History count.
2. **There is no detail pane.** Selecting a row opens nothing. A row shows what a user needs to know
   about that job.
3. **The row anatomy** — thumbnail, title, uploader and duration, progress and state. *(This read
   "both tabs draw the same row anatomy" and described what History changed about the fields; the
   anatomy is unchanged and now has one surface drawing it.)* **[T]** `UX-005`, **amended
   2026-08-14** (`T201-R3`): **a failed row that has an honest next step is one line taller**, and
   that line says what the user can do. Where there is nothing honest to suggest — `DRM_PROTECTED`,
   `GEO_RESTRICTED` — the row keeps this anatomy exactly. §2's ban on a detail pane is why the line
   is here at all: `NFR-006` asks for what failed, why, and what to do, and the row is the only
   surface there is for the third.
4. **Every verb the row's state permits is on its last line**, right-aligned, sharing that line with
   the format control, plus `⋯` for the rest — which is also the keyboard route.
5. **Nothing is drawn disabled and nothing is drawn that would be refused.** A row offers what its
   state permits and says nothing about the rest.
6. **The per-row format control appears only while `retarget()` would accept it**; it is plain text
   once a download starts.
7. **There is no per-job pause.** `pause()` is queue-wide, in-flight sessions finish, and a waiting
   row reads **Held**, never *Paused*. **[T]** `UX-006` (2026-08-07) makes that gate the queue's
   normal resting state rather than an interruption: a queue is **stopped until started**, so a row
   added to one reads **Held** from the moment it is enqueued. The word does not change and neither
   does the drain; what changes is which side of the gate the window opens on.
8. **A finished download stays in the Queue tab** with *Open* and *Show in folder* until
   *Clear finished* moves it on.
9. ~~**History removal is selection-scoped**, its verb names its own count, and *"files are never
   deleted"* sits in the status bar while History is showing.~~ **Withdrawn 2026-08-06**: there is
   no list, and no records behind it either. `DAT-005`'s boundary — a record is not a file — is
   untouched and governs anything that ever stores one again.

### 2.1 The toolbar

**[T]** `UX-005` (2026-08-04 amendment), `DAT-005` (2026-08-05 amendment), `UX-006`
(2026-08-07) and `UX-013` (2026-08-12). `+ Add URLs` first, as the primary action; the **run
control**; and `Clear finished`. **Three verbs and nothing else.**

*(The `Concurrent downloads` control stood here too, which `ARC-007` put in the window "until
Phase 4's settings dialog replaces it". That dialog exists — `T-146` — so `UX-013` completed the
sentence: the limit is set in `Settings → Settings…` and nowhere else. `T-234` builds the removal.
The clause is worth keeping as history because it is the shape of every stopgap: the condition for
undoing it was written down, met, and then went unnoticed for a phase.)*

**[T]** **The run control is one control with two states, and the queue opens stopped** (`UX-006`).
It reads `Start` while the queue is stopped and `Stop` while it is running — the same single
checkable action `Pause queue` already was, renamed to what it now governs. *(It read `Pause queue`
until 2026-08-07, when the queue stopped running by default and "pause" became the wrong word for
the state a window opens in.)*

**[D]** **A stopped queue holding work says so where the work is.** Derived from `UX-005` §5 —
nothing is drawn that would be refused, and its converse, that a state which blocks a user's
expectation is stated — plus `NFR-005`'s rule against colour alone. A queue that shows waiting rows
and nothing else is the one state in which a user can reasonably conclude the application is
broken.

**[T]** **`T-181` chose the treatment, 2026-08-07: a permanent status-bar statement**, reading
*Queue stopped — press Start to download* or *Queue running*, beside the environment summary. It
names the remedy and not only the state, because a user looking at a full queue and no activity
needs to be told what to press. The run control's own tooltip carries the same state, which is what
a toolbar button publishes as its accessible description — the checked tick is a visual cue and
cannot be the only one.

**It is said in two places, and they answer different questions** (corrected 2026-08-07 by
`T181-R1`). The status line answers *why is nothing happening* for the window; **§2 item 7's
waiting row reads `Held`** and answers *what is this row waiting for*.

*This paragraph previously recorded that the row was deliberately not built*, on the reasoning that
a queue-level fact belongs at queue level. **That reasoning was mine and it cannot stand here**:
`UX-006` item 3 is an accepted maintainer decision requiring the row to read `Held`, and a
current-truth paragraph in this file cannot amend one — `T124-R4`'s rule, which this project has
now recorded twice. The row is built, it repaints when the gate changes, and `UX-001`'s
distinction survives intact: the gate is still a property of the queue, and the row reads it
rather than storing one.

**`Clear history` left the toolbar with the list it emptied** (2026-08-06), and nothing replaced it:
`REQ-020` was withdrawn the same day, so there is nothing anywhere to clear. `Clear finished` stays
— it clears completed **queue rows**, and with no records beside it there is nothing left for it to
be confused with. **[T]** *(built 2026-08-10 by `T-146`)* **`Settings` is a menu between `File`
and `Help`**, and the screen behind it holds **all eight** <!-- req023:count built=8 total=8 --> of `REQ-023`'s settings — the download
folder, the theme, and the concurrency limit (`T-146`; the toolbar showed it too until `UX-013`
moved it here alone), the ffmpeg location
(`T-199`), the cookie source (`T-197`), the default preset and output template (`T-195`), and the
network options — proxy, speed limit and retries — from `T-196`, which was the last of the eight.
The screen's *"still to come"* sentence is empty and its label is not built, so it claims nothing
either way; `docs/DEVELOPMENT.md` carries the table.
*(There was no Settings menu between 2026-08-06 and then: the shell built to hold the withdrawn
records control went with the control.)*

**The rule the toolbar keeps:** nothing on it acts on a *selection*, and every verb on it names the
list it empties.

### 2.2 The state chip

**[T]** `UX-005` (2026-08-04). A chip on the title line carrying **words**, never colour alone
(`NFR-005`): `Done`, `Queued`, `62%`, `Failed`. *(This read "Queue tab only", against a History tab
whose every row was finished. There is one surface now and the rule is unchanged.)*

**[T]** A *group* header is the exception. **A queue group's chip is progress — `0 of 3`, done of
total — and never a percentage** (`UX-010`, 2026-08-09): the entries' totals arrive one at a time,
so a fraction across them has a denominator that grows while it runs. *(This clause read "its chip
is a **count** of the members present — `16 items` … Never `14 of 16`. This was written for
History's groups and holds for the queue's" — extending `T-145`'s History ruling past its own
reasons. History's denominator claimed records the list did not hold; every member of a live queue
group is present. The built chip and this clause disagreed from the day the History tab was
withdrawn, found 2026-08-09 by a screenshot put beside the spec; `UX-010` ruled for the build.)*

---

## 3 · The add dialog: a staging list

**[T]** `UX-003`. **Nothing enters the queue unprobed.** A paste resolves in place, each line
becoming a row carrying its title, uploader, duration and thumbnail, and *Add to queue* commits what
resolved.

- **[T]** A URL that will not probe never becomes a job. It stays in the dialog with the extractor's
  message verbatim (`NFR-006`) and its own retry; the commit button counts only what resolved.
- **[T]** Probe state is shown in the dialog and nowhere else.
- **[T]** `UX-004`: every row carries a **visible** *Download as* control showing what it will be
  downloaded with, and a row that has not been overridden shows the batch preset explicitly as
  inherited — never blank, which reads as *none* rather than *the one above*.
- **[T]** `UX-004`, *shape ruled 2026-08-30 by the maintainer (`T-284`)*: **the control shows the
  preset's name and nothing else**, and **the editor's inherited entry shows that name followed by
  *— following the batch***. The relation lives on the row's detail line — *"Download as: … —
  following the batch"* — so both facts are on the row without crowding a control whose label field
  measures **around 146 px** once the frame, the arrow and the `⋮` zone are taken out of it — the
  exact figure is the style's, 146 offscreen and 148 through the production dark sheet. **The name
  alone does not always fit that field** — two of the five built-in presets are wider, the default
  among them — so the control **elides with an ellipsis** and the row's detail line carries the
  value in full (*ruled 2026-08-30; the 2026-08-28 ruling had assumed this shape never elided, and
  measurement refuted that*).
  The entry carries the value as well because the closed control and the open editor must agree on
  it: a relation-only entry renames what the user clicked at the moment of the click. *This
  replaces `Same as all`, which delivered the relation and dropped the value the line above asks
  for.*
- **[T]** *(amended 2026-08-09 by `UX-011`; the combo half is built by `T-203`)* **The control
  holds presets, full stop** — every entry in it is a value that sticks, and no entry opens a
  window. The four commands it had accumulated by Phase 3's end — `Choose specific formats…`,
  `Options…`, `Where it goes…`, `Manage presets…` — are gone from it: the first three move to the
  row's own menu below, the last to the dialog footer (`UX-009`). *The control looked like a value
  picker while containing commands, and appeared to accept a choice it discarded — the
  maintainer's own misreading of it in review is the evidence.*
- **[T]** *(ruled 2026-08-09, `UX-011`; `T-203` builds it — option E, round 8)* **The three
  per-row verbs live in the row's menu**: `Choose specific formats…`, `Options…` and
  `Naming and folders…`, under a *Just this item* heading, above the Retry/Remove entries that
  menu already holds. The menu opens **two ways**: from a `⋮` zone drawn on the trailing
  edge of the row's format control, and by the routes the row's context menu already answers —
  right-click, the Menu key, Shift+F10. One menu, not two lookalikes.
- **[T]** *(ruled 2026-08-10, `UX-012`; `T-223` builds it)* **The menu holds nothing that only
  focuses a visible control.** The `Choose a format for this URL…` entry — `T118-R9`'s
  discoverability alias for the keyboard editor route — is gone: the combo is visibly on the row,
  and the keyboard reaches it through the edit key, not through a menu entry. **And Remove names
  what it removes**: a playlist row's entry reads `Remove this playlist (N items)` with the row's
  real entry count, because removing the line removes the batch and the label owes the user that
  blast radius; a single item keeps `Remove this URL`. The label is the opened-from row's own
  content — no current-row announcement returns.
- **[D]** *(`UX-011`)* **The menu is anchored to the row it acts on, so the target is structural.**
  A shared control acting on "the current row" must *say* which row that is — that obligation is
  what `T203-R1` was. A menu opened from a row cannot act on any other row, so no target label or
  announcement machinery exists to drift.
- **[T]** *(`UX-011`; amended 2026-08-10 by `UX-012`, `T-224` builds it)* **The painted `⋮` is an
  affordance, not the only door — and it is drawn as a button, not bare punctuation.** The
  maintainer's live-use report — *"not a very pronounced button, people might even miss that they
  are there"* — is the zone failing at discoverability, which is its only job, so it gains a drawn
  border and a hover/pressed state while keeping its one-definition geometry for paint and hit
  test. The delegate still paints it, so it has no accessibility node — the same fact that
  rejected the icon shapes — and that stays acceptable for the reason the painted disclosure
  triangle already is: the function it exposes has a fully accessible sibling route (the Menu
  key / Shift+F10 menu), and the menu's items are real widgets a screen reader announces.
  *`UX-011`'s option G — dropping the zone — remains the recorded fallback if the strengthened
  zone still fails.*
- **[T]** `UX-004`, *route shared since `UX-011`*: Retry and Remove are a context menu, reachable
  by the Menu key and Shift+F10 as well as by pointer — the same menu the `⋮` opens, so the row
  has one "more" place rather than two.

---

## 4 · The format table — `REQ-003`, built by `T-107`

`REQ-003`: *show the available formats for a probed URL in a sortable table (format ID, extension,
resolution, fps, codecs, bitrate, filesize/estimate, notes).*

### Legibility, ruled 2026-09-09

**[T]** **The codec columns show the name, and keep the identifier in the tool tip.** `avc1.640028`
reads as `H.264`, `vp09.00.40.08` as `VP9`, `av01.0.08M.08` as `AV1`. `REQ-003` asks for codecs and
does not say in whose vocabulary; `REQ-009`'s selector syntax and every bug report are written in
the identifier, so it stays reachable rather than being replaced. A string the table cannot read —
archive.org's `h264-hd` — is shown as written rather than guessed at.

**[T]** **A chosen row marks itself.** The footer names the selection in words for `NFR-005`, and
until this the table itself agreed with it nowhere, which made a two-step merge selection a thing
you had to hold in your head.

**[T]** **The format id column is drawn quieter than the rest of its row.** It stays — `REQ-003`
names it and `REQ-008` selects by it — but it is almost never why a person is reading the row, and
it was the strongest thing in it.

*Ruled by the maintainer on 2026-09-09, from a session with the built window: "there isn't an easy
way to see what you are picking, and most people won't know the number codes". **A fourth option —
the table recommending a row — was declined** in the same ruling: it would make this surface
advisory, which is what presets are for. `T-306` carries the work.*

### Where it lives

**[T]** *(amended 2026-08-09 by `UX-011`; `T-203` builds it)* The table opens from the staging
row's **menu** — its `Choose specific formats…` entry, the first under *Just this item* (§3).
*Until `T-203` it opened from an entry of that name inside the row's format control; the control
holds presets only now. The queue row's *Download as* control (`UX-005` §6) is a preset retarget
and is not a route to the table — this clause once named both surfaces as one control, and they
never were.*

**[T]** **It opens as the staging row itself, expanded** — not as a modal dialog (`UX-007`,
2026-08-07). *This file proposed the modal and was ruled against.* A modal opened from the add
dialog is a modal over a modal, and the staging list is already a list of rows that open; `P-19`
takes the same shape for the playlist picker, so the two surfaces are **one mechanism** rather than
two. `UX-005` §2's ban on a detail pane ruled out the obvious home and left three candidates; this
is the one that reuses something already built.

### Two lists, not one grid, ruled 2026-09-09

**[T]** **Video and sound are separate lists, side by side, each carrying only the columns its own
kind has.** A video list does not ask a video what its audio codec is; a sound list does not ask an
audio stream for its resolution or its frame rate.

*Ruled by the maintainer on 2026-09-09, from ten mockups built on the real widget
(`tools/split_tables_mockup.py`, option `N`): "the video and audio codecs aren't clearly separated
(all just in one big list)" and "the options with audio AND video aren't even selectable". `T-310`
carries the work.*

**The two findings had one cause and this is it.** One grid forces one set of columns, so a
video-only row had to answer *audio codec* — and `T-305` could fix that cell's vocabulary but not
remove the question. One grid also invites a **mode** to say which kind is being picked, and that
mode is what refused the formats already carrying both streams (§5).

- **[T]** The **Video** list holds video-only formats, then formats that already carry sound
  **grouped last**, then formats the source did not classify. A `Sound` column reads `add one`,
  `included · <codec>`, or `not stated`. *The grouping is the maintainer's: "list the video with
  attached audio last in the list together."* It survives every sort — the column sort runs first,
  then a second stable pass sinks the group, because a compound key would float the group to the
  top on any descending sort.
- **[T]** The **Sound** list holds audio-only formats. **[D]** When a source offers no audio half
  at all, the list is replaced by the reason **in its own place** — `P-13`'s rule, applied to the
  surface that replaced the mode `P-13` was written about. `ui/format_selection.py` records that
  *"most formats from most sources are `UNKNOWN`"*, so this is the ordinary case on archive.org and
  PeerTube, not an edge. **Absent ffmpeg is not this case** and does not remove the list — see §5.
- **[T]** **Every format the probe returned appears in exactly one list — with the two exceptions
  ruled below and no others.** One nothing was said about is *not* an exception: it goes in the
  video list. A format that vanishes because it could not be classified would be this surface
  failing `REQ-003` quietly, which is the failure this clause exists to forbid.

**[T]** **Columns run decision, then compatibility, then provenance.** `Quality` leads *every*
list, so the eye reads down one left edge rather than a different first column per list; `Size`
follows. `Bitrate`, `File type` and `ID` come last — each is a fact `REQ-003` requires and none of
them is why anyone clicks. `ID` is last of all, carrying `T-306`'s quieter-ink ruling from emphasis
into position.

**[T]** **The codec column is the codec.** An earlier revision glossed it — `VP9 — smaller, widely
played`. *Ruled out by the maintainer the same day: "anyone hand selecting the audio/video stream
will hopefully know what they are doing."* That is a statement about who arrives here, and the
right one: this table is reached through a row menu's `Choose specific formats…`, and the presets
are the path for everyone else. `T-306`'s tool tip keeps the raw identifier reachable.

### What it shows

- **[T]** Every column `REQ-003` names — format ID, extension, resolution, fps, codecs, bitrate,
  filesize or estimate, notes — **in the list where it means something**, rather than every column
  on every row.
- **[T]** Sortable. **[D]** Sorting is over the **projection**, not the display string: `1080p` sorts
  after `720p` and `144p`, and `~12.4 MB` sorts as a number. Derived from `T-075`, which is the
  defect of a table sorting its own text.
- **[D]** A format missing a field renders the placeholder the rest of the window already uses
  (`UNKNOWN_TEXT`), never an empty cell and never `None`. **A field yt-dlp denied reads `None`
  rather than *unknown*** (`ABSENT_TEXT`, `T-305`): a video-only format has no audio codec and a
  format with nothing noted has no note, and reporting either as unknown is a claim about
  something the extractor stated. Derived from `_text_or_absent`'s rule.
- **[D]** The table reads a `FormatInfo` projection, never raw `info_dict` keys. Derived from
  `NFR-008` and `ARCHITECTURE.md`'s declared-fields-only rule.

### Keyboard path — `NFR-005`

**[D]** Throughout, derived from `NFR-005` and the routes `T-124`/`T-152` already established.

| Key | Does |
|---|---|
| Menu key / Shift+F10 on the row, then `Choose specific formats…` | Opens the table for that row |
| `Tab` | Moves between the header row, the table body and the buttons |
| `↑` `↓` | Move the current format |
| `Space` on a header | Sorts by that column; again reverses |
| `Enter` | Chooses the current format. **Does not close** — see below |
| `Esc` | Closes, choosing nothing |

The table opens with a **current row** already set, because a declared keyboard route that needs a
click first is not one (`T-152`).

**[T]** **Choosing never closes the panel** *(amended 2026-09-09 by `T-310`; this row read "chooses
the current format and closes")*. That was written for a single grid where one press ended the
interaction. With two lists a choice is rarely the last thing a person wants to do, and closing on
it takes the surface away mid-task — most sharply on the second half of a pair, where the panel
vanished the instant the audio row was taken. *Ruled by the maintainer from the built window: "the
user should have to say 'Done' or 'Apply' before that happens."* Closing is only ever asked for:
`Done`, the disclosure triangle, or `Esc`. Nothing is lost by staying open — the choice is written
to the row as it is made, and `Esc` still undoes it.

**[T]** **Two kinds of entry are not listed at all** *(2026-09-09, `T-310`)*, and both are the
maintainer's ruling from the built window rather than a filter `P-14` would refuse:

- **An entry carrying neither stream** — yt-dlp wrote `vcodec: 'none'` **and** `acodec: 'none'`,
  so it is a storyboard or a thumbnail sheet rather than a format. *"If you can't select them, why
  are they even there?"* **[D]** Read from the explicit denial, never from `kind_of`'s `UNKNOWN`:
  that state also means *nothing was said*, which is what archive.org and PeerTube report for
  everything they publish, and refusing on the kind would empty this surface on those sites.
- **A row with nothing to choose it by** — no codec, no bitrate and no size, so every column that
  could tell it apart reads *Unknown*. *"To the typical user those are just noise and additional
  clutter."* **[D]** Kept when they are all a list has: a real HLS audio rendition arrives with no
  codec named, and on a source served entirely over HLS those rows are the only sound there is.

### Deliberately not offered

**[T]** *(ruled `P-14`, `UX-007`)* All three. `REQ-003` asks for a sortable table and is silent on each of these, so they
are choices about scope rather than consequences of it.

- **No re-probe from the table.** What it shows is the probe the row already has. A refresh button
  implies the list goes stale within a session, and nothing establishes that it does.
- **No download from the table.** It chooses a format; committing is still the dialog's button.
- **No filtering or search.** A filter is a second interaction to learn for a list that is dozens of
  rows at worst.

  > **[D]** **Separating video from sound is not a filter** (2026-09-09, `T-310`). A filter is a
  > control the user operates to hide rows. These are permanent, labelled, simultaneously visible
  > lists, and no row is hidden from the list it belongs to. The clause stands unamended.
  >
  > **Two kinds of entry are not listed at all**, ruled separately and named above: one carrying
  > neither stream, and one with nothing to choose it by. Those are decisions about what counts as
  > a format this surface offers, not a control that hides rows from a list — which is what `P-14`
  > refuses.

---

## 5 · Choosing video + audio — `REQ-008`, built by `T-108`

`REQ-008`: *allow selecting specific format IDs directly from the format table, including a separate
video and audio stream to be merged.*

- **[T]** *(ruled `P-2`, `UX-007`)* The table has two selection modes: **one format**, and **video + audio**. In the second,
  a row is chosen into whichever of the two slots its own kind matches, and the dialog shows the
  pair it will merge before it is committed.

  > **[T]** **Narrowed 2026-09-09 by `T-310`: the two selections remain and the *mode* does not.**
  > `P-2`'s routing is kept in full — a row still goes to whichever slot its own kind matches, and
  > the pair is still shown before it is committed. What is deleted is the **control** that asked
  > the user to declare which mode they were in before they had anything to declare it about, and
  > with it the refusal that control required.
  >
  > **The refusal is the reason.** `FormatSelection.choose` raises `UnplaceableFormatError` in
  > `PAIR` for a format that carries both streams — so the two formats needing no merge at all were
  > the two the merge mode would not accept. The maintainer found it from the built window and
  > named it exactly: *"the options with audio AND video aren't even selectable"*, and then *"if
  > someone wants to individually select the video and audio track separately, why would they pick
  > one that had both below?"* They would not; the question is not one to ask them.
  >
  > So the selection is now a **consequence of what was picked**, and nothing is refused. A format
  > carrying both streams is the whole download. One carrying video alone fills the video half. One
  > carrying audio alone fills the sound half. One the source did not classify is the whole
  > download too, because nothing about pairing it can be asserted — which is `kind_of`'s own
  > reading of `UNKNOWN`, not a new one.
  >
  > `UnplaceableFormatError` stays in `ui/format_selection.py`. It is unreachable from this surface
  > and it is still the honest answer for any caller that routes into a declared slot.
- **[T]** *(ruled `P-13`, `UX-007`)* `Merge` is offered only while ffmpeg is present. Absent, the mode is **not drawn**, and
  the reason is stated where the mode would have been.

  > **[D]** **The rule outlived the control it was written about** (2026-09-09, `T-310`), and both
  > its sentences survive it. There is no mode to draw or not draw, so:
  >
  > - **ffmpeg absent** — the reason is stated beside the lists, where somebody assembling a pair
  >   will read it, and `merge_refusal` refuses the pair itself at commit (`REQ-024`).
  >   **The sound list is not hidden.** An earlier draft of this amendment said it was, and that
  >   was wrong in a way worth recording: an audio-only format is a perfectly good download and
  >   needs no ffmpeg to fetch, so suppressing the list would have made those formats unreachable
  >   on exactly the machines least able to work around it. `P-13` withheld a **mode**, not a
  >   catalogue.
  > - **The source offers no audio half** — there is no sound list to draw, and the reason stands
  >   in its place. This is `P-13`'s own shape, and the sentence is the one `pairable` already had.
  >
  > The two stay separate for `P-13`'s own reason: telling somebody to install ffmpeg for a source
  > that would not merge anyway is advice that cannot help. `UX-005` §5's never-draw-what-would-be-refused
  rule makes *some* treatment necessary; it does not choose between hiding the mode, showing the
  table without it, or admitting the choice and refusing at commit. `REQ-024` owns the detection.

- **[T]** **Two different facts, and conflating them is how `T-061` happened** (`T105-R2`).

  1. **The table knows its own pair needs a merge.** A user who has explicitly chosen a video format
     and an audio format has stated a merge; nothing needs inferring, and no selector is parsed.
  2. **The worker's gate is the definitive one, and it reads the *resolved* formats.**
     `_ffmpeg_gap` asks `_will_merge(info)` — yt-dlp records a merge by populating
     `requested_formats` with more than one entry — and inspects `request.format_selector` **only
     when resolution supplied no answer at all** (a playlist, or an extraction that stopped before
     format selection), where being wrong costs a refusal rather than the user's bandwidth.

  *This file first said the gate reads "the resulting selector, not the chosen format, which is
  `T-061`'s finding exactly". That is backwards, and it is the route straight back to the defect:*
  `bestvideo+bestaudio/best` *against a source offering one progressive format resolves through*
  `/best` *to no merge at all, and the selector-reading gate refused it anyway — measured
  2026-07-28. The task's **title** names the defect; its **status line** names the fix.*
- **[D]** Choosing a pair writes one request whose selector is the two ids joined. What the row then
  *says* is the shared naming rule's answer (`ui/format_text.py`), not the raw selector — which is
  `T140-R3`, `T126-R2` and `T-159`, all three of which were this same defect.

### Keyboard path

**[D]** *(superseded 2026-09-09 by `T-310`; the original is kept because the announcement rule it
carries is unchanged and still load-bearing.)* ~~The mode is a control in the table's own frame, so
it joins the `Tab` order ahead of the header row — a mode that changes what `Enter` does must be
reachable before the thing it changes. `Space` switches mode~~ — **there is no mode control**, so
`Tab` runs video list, sound list, then the panel's own way out, and each list's `Enter` chooses
from that list. In **video + audio** the two chosen rows are announced as *"video: 137, audio:
140"* rather than shown by highlight alone (`NFR-005`, no colour-only state), which is unchanged.

### Deliberately not offered

**[T]** *(ruled `P-15`, `UX-007`)* Both. `REQ-008` names *"a separate video and audio stream"*, which neither entails nor
forbids what follows.

- **No three-way merge**, and no external audio file. yt-dlp's selector permits more than this
  application offers, and `REQ-009`'s custom selector is the escape hatch for it.
- **No automatic pairing suggestion.** Guessing "best audio for this video" is a preset's job, and
  the presets already do it.

---

## 6 · Post-processing — `REQ-010`, built by `T-109`

`REQ-010` names seven: extract/convert audio to a chosen codec and quality; remux container; recode
container; embed thumbnail; embed metadata; embed chapters; embed or write subtitles with language
selection.

### The structural observation this deliverable turns on

**[D]** **All seven are preset-owned, though only two of them have a field of their own.** `Preset`
declares `audio_codec` and `audio_quality` (option 1) and `embed_subtitles` and
`subtitle_languages` (option 7); the remaining five — remux, recode, embed thumbnail, embed
metadata, embed chapters — have no dedicated field and would ride in `post_processors`, a list
`Preset` already declares. Every one of those names is in `PRESET_OWNED_FIELDS`, which is derived
from the two dataclasses rather than listed.

**[T]** *(ruled `P-16`, `UX-007`)* **That `T-109` and `T-111` therefore share one screen is a choice, not a consequence**
(`T105-R3`). What the data boundary establishes is that these options are preset-owned and that
`to_request()` refuses an override disagreeing with the preset the user was shown (`T015-R1`) — it
does not follow that one widget must edit both a saved preset and a one-off. The argument for
sharing is that a separate panel is a second place to set the same fields; the argument against is
that a per-download tweak and a stored preset have different save semantics, which `P-3` and `P-4`
are already circling. **Ruling on this decides whether `T-109` has a screen at all.**

**[T]** *(ruled `P-12` by **`ARC-010`**, not `UX-007` — it was answered from above, as part of the
option-coverage decision, rather than in the §10 session)*
**Whether the five undedicated options get fields of their own is `T-109`'s first
question.** A `post_processors` list of opaque strings is what `Preset` has today; five booleans
would be typed, checkable and visible to `PRESET_OWNED_FIELDS`'s drift test, at the cost of widening
a model Phase 1 froze. This file does not decide it, and flags that a UI cannot be specified past
it: five checkboxes and one free list are different screens.

> **[T]** **Answered 2026-08-07 by `ARC-010`: typed.** The five get fields of their own, and the
> model widens. The decision took the question one level up — every option group faces it, not just
> post-processing — and ruled that a user-facing option is a typed, validated field, with one
> validated **escape hatch** (`REQ-031`) carrying what has no field yet. This clause stays because
> `T-109`'s screen has not been specified against the ruling yet; the question behind it is closed.

- **[T]** *(ruled `P-3`, `UX-007`; route amended 2026-08-09 by `UX-011`, which `T-203` builds)*
  The editor is reachable **two ways**: as the row menu's *"Options…"* entry, editing a one-off
  choice for this download only *(until `T-203`, an entry of that name on the format control)*;
  and from the preset manager (§8), editing a saved preset. The same widget in both, with a
  different title and a different save action. **`P-3`'s substance is untouched** — what moved is
  where the per-item entrance sits, not that it exists.
- **[D]** Audio quality is offered only for a codec where a bitrate means something — `MP3_BITRATES`
  is MP3's scale, and `with_audio_quality` already refuses any other codec for that reason
  (`T076-R1`).
- **[T]** *(ruled `P-4`, `UX-007`)* A one-off options change **does not** silently become a preset. The editor offers
  *"Save as preset…"* explicitly.
- **[P]** *(`T-222`, 2026-08-11; **ruled `[P]` by review at `T222-R2`**, demoted from `[D]`)*
  **The four option groups scroll; the save line and the buttons do not.**

  **This was written as `[D]` and the reviewer ruled it a product choice, correctly.** My argument
  was that the height has to come from somewhere and the other two places were measured worse, so
  scrolling followed. What measurement actually establishes is that the old layout clips and that
  two floor-raising candidates are worse — it does not choose *which region* scrolls or *which
  controls stay fixed*. Those are presentation decisions, and `T145-R1` and `T144-R1` are on record
  as what it costs when I record one as a derivation.

  **The defect it answers is not in dispute.** The dialog opened at 302 by 680 — its own reported
  minimum — with the Container group's explanation cut to one of its two wrapped lines: no
  scrollbar, no ellipsis, nothing to say a sentence had lost half of itself. A word-wrapping
  `QLabel` reports a one-line minimum, so Qt is free to take height out of explanatory text to make
  a short window's arithmetic work.

  **Built ahead of ratification, on the reviewer's explicit instruction** — *"Demote the clause;
  this ruling does not require unbuilding the scroll-area correction."* §1's bar says no task may
  build a `[P]` clause until it is ratified, and this one is in the tree, so the exception is
  recorded here rather than left to be discovered. What is open for the maintainer is whether
  scrolling is the right shape, not whether the clipping needs fixing. See §10.

### Keyboard path

**[D]** A form, so the platform's own order applies: `Tab` between fields, `Space` toggles a
checkbox, arrow keys move within a combo, `Enter` commits, `Esc` cancels. **[T]** Every control
carries a screen-reader label (`NFR-005`).

**[T]** *(ruled `P-17`, `UX-007`)* **The subtitle language control is a labelled multi-select** rather than a
comma-separated text field. `NFR-005` requires the control to be labelled and reachable; it does not
choose the widget, and `SUBTITLE_LANGUAGES` is `("all",)` today, so the set a user picks from is
itself unspecified.

### Deliberately not offered

**[T]** *(ruled `P-18`, `UX-007`)* Both, and the first interacts with `P-12`: refusing a free-text post-processor field
while `Preset.post_processors` is a list of strings means the model can express what the UI will
not, which is an argument for typing those five options rather than a separate choice.

> **[T]** **Narrowed 2026-08-07 by `ARC-010`.** A free field exists, and it is not this one: the
> escape hatch is *additional yt-dlp options* on the **request** (`REQ-031`), parsed and validated
> against containment, redaction and the application's own option keys — not a raw list of
> post-processor names handed to `build_options`. So the refusal this clause proposed stands for the
> post-processor list, and the capability it was refusing is reachable through a checked route.
> Per-entry post-processing is untouched and still `T-110`'s question.

- **No arbitrary yt-dlp post-processor list.** `REQ-010` names seven; a free-text field would be an
  unbounded surface with no way to say what it will do.
- **No per-entry post-processing inside a playlist.** `UX-005` row 9c has entries inherit their
  group's format, and splitting that per entry is a decision nobody has asked for.

---

## 7 · Playlist entry selection — `REQ-004`, built by `T-110`

`REQ-004`: *for a playlist, let the user select which entries to enqueue, including select-all and
range selection, before any download starts.*

- **[T]** `UX-003`'s consequence: *"Phase 3's playlist picker gets its prerequisite for free"* — a
  playlist expands into entries only after a probe, which `UX-003` guarantees has happened by the
  time a row exists.
- **[T]** *(ruled `P-19`, `UX-007`)* The picker is the **staging list's own row**, opened, rather than a separate dialog.
  The supporting argument is that the queue and History already draw a playlist as one row that
  opens (`T-140`, `T-145`). It is **not** entailed by `UX-005` §3, whose one-anatomy rule is about
  the Queue and History tabs and says nothing about the add dialog (`T105-R3`).
- **[T]** *(ruled `P-5`, `UX-007`)* Each entry carries a **checkbox**, and the group header carries a tri-state checkbox
  reflecting its members. *Add to queue* commits only the checked entries.
- **[D]** Unchecked entries are **not** queued and not remembered. Nothing is persisted until Add is
  pressed (`UX-003`), so there is no state to keep.

### Keyboard path

| Key | Does |
|---|---|
| `→` / `←` on a header | Opens / closes the playlist — the route `T140-R5` established |
| `Space` | Toggles the current entry, or the whole group on a header |
| `Shift`+`↑` `↓` | Extends a range |
| `Ctrl`+`A` | Selects every entry |

**[D]** Range and select-all are `REQ-004`'s own words, and the keys are the platform's conventions
rather than new ones.

### Deliberately not offered

**[T]** The first. **[T]** *(ruled `P-25`, `UX-007`)* The second.

- **No reordering of entries.** `REQ-016`'s reordering predates grouping and does not say what it
  means inside one — `T-142`'s out-of-scope list already records this, so it is transcribed rather
  than chosen here.
- **No filtering by title or duration.** A picker that hides entries can lie about what *select all*
  did — which is an argument, not an authority. `REQ-004` is silent.

---

## 8 · User presets — `REQ-007`, built by `T-111`

`REQ-007`: *create, edit, duplicate, delete, set one as default.*

- **[T]** *(ruled `P-6`, `UX-007`; route amended 2026-08-09 by `UX-009`, built by `T-203`)* A
  **preset manager**, reached from the add dialog footer's `Manage presets…` button — **disabled
  rather than hidden** when composition wires no manager, per `UX-005` §5's own rule. *Until
  `T-203` it was an entry on the format control, offered once per row on every row because the
  combo was the only place it could go; `UX-009` rules that a library-wide action does not belong
  on a row.* It lists built-ins and the user's own together, with the built-ins not deletable and
  marked as such.
- **[D]** A built-in cannot be edited in place. `custom_preset` and `with_audio_quality` already
  derive a new preset rather than mutating one, because a request that disagrees with the preset the
  user was shown defeats `REQ-009`. Editing a built-in therefore **duplicates it first**, visibly.
- **[T]** *(ruled `P-7`, `UX-007`)* The default preset is what a new paste inherits. One default, always set; clearing it is
  not offered, because the dialog needs *something* to inherit.

### Keyboard path

**[T]** *(ruled `P-20`, `UX-007`)* **A list beside a form**, with create, duplicate and set-default as buttons in the
list's own `Tab` order rather than a context menu. `T118-R5` establishes that a menu-only route is
not authority to *drop* an approved visible control; it does not choose this layout, and `NFR-005`
requires reachability rather than any particular arrangement (`T105-R3`).

**[D]** Within whatever layout is ratified: `Delete` on a built-in **does nothing and is not drawn
disabled** — `UX-005` §5 is explicit that nothing is drawn that would be refused, so the built-in is
marked as one instead.

### Where presets persist — already decided, and this file had it wrong

**[T]** **TOML, in the existing settings store.** `DAT-001` is titled *"SQLite for queue and
history; **TOML for settings**"* and its body says *"TOML (in `user_config_dir`) for settings **and
user presets**"*. `ARCHITECTURE.md` §5 fixes the owner and the exact path: `core/settings.py`,
`user_config_dir/tracksandtrails/settings.toml`. `ARC-007` implements that boundary and does not
reopen it.

**No new SQLite table, and no sibling file** (`T105-R1`). This section first raised the question as
`P-8`, *"where user presets persist is a `DAT-` decision"* — it was answered before it was asked.
The error is worth leaving visible: `T-111`'s own risk line says *"persisted state, and where it
lives needs a decision"*, and this file trusted that sentence instead of reading `DAT-001`. A task
entry is not an authority for what a decision entry has settled. `T-111`'s line is corrected too.

A **TOML schema** question may still be raised if the implementation exposes a durable trade-off —
that is a different question from where the file lives, and it is not open today.

### Deliberately not offered

**[T]** *(ruled `P-21`, `UX-007`)* Both. `REQ-007` names five verbs — create, edit, duplicate, delete, set default — and is
silent on the rest, so these are scope choices.

- **No import or export of presets.** A sharing format is a compatibility commitment.
- **No per-site presets.** Nothing asks for it, and it would need a matching rule nobody has specified.

---

## 9 · The rest of Phase 3

### 9.1 Output template editor — `REQ-011`, built by `T-112`

- **[T]** *(`UX-011`; the rename is built by `T-203`, the menu route it builds next)* **Reached
  from the row menu's `Naming and folders…` entry** — renamed from `Where it goes…` on maintainer
  direction, because that label promised a folder picker and opened a `%(field)s` template editor,
  and the maintainer's own misreading of it as a destination picker was the evidence. Where files
  *root* is `REQ-023`'s download directory, on the settings screen (`T-146`, built 2026-08-10);
  the two are named apart so they cannot be confused, and both now exist. **Whether the per-item
  template itself survives is `REQ-011`'s open ruling** — `UX-011` moves its entrance and
  deliberately does not take that ruling by implication.
- **[T]** `REQ-011` as amended (2026-08-01, `T046-R2` and `T046-R4`): a live preview of the resulting
  path, **labelled as the *intended* path** wherever the final container is yt-dlp's to choose.
  Audio extraction to a **named** codec previews exactly, through yt-dlp's own `ACODECS` table — the
  codec is not the extension, since `aac` and `alac` both land in `m4a`.
- **[T]** *Audio only (original)* is **provisional** and says so: `best` keeps the codec rather than
  the container, and yt-dlp decides by running `ffprobe` on the downloaded file.
- **[D]** Preview and the real write are **one function**. Two would drift, which is the whole of
  `T-046`'s finding.
- **[T]** Path containment is **enforced**: no rendered template escapes the output directory.
  That is Phase 3's fourth exit criterion and `ARCHITECTURE.md` §8's rule, not a choice.
  **[T]** *(ruled `P-23`, `UX-007`)* That the refusal is shown **at edit time, with the reason**, rather than at download
  time, is the choice — it is better feedback and it costs a validation path that runs on every
  keystroke.
- **[T]** **Keyboard path:** a single-line input with the preview below it as a **focusable
  read-only field** — a second stop in the tab order (`UX-007`, 2026-08-07). *This file proposed an
  unfocusable live region and was ruled against, on its own argument:* a user who cannot `Tab` to
  the preview cannot review it at their own pace, and a live region announces on the writer's
  schedule rather than the reader's. It costs one tab stop, which is the price of the preview being
  reviewable rather than merely audible.
- **[T]** *(ruled `P-9`, `UX-007`)* The editor lists the template fields it supports beside the input, rather than linking
  to yt-dlp's documentation, because the set this application supports is not yt-dlp's whole set.

### 9.2 Resume across a restart — `REQ-017`, built by `T-113`

- **[T]** `REQ-017`: resume where the site and format allow it, **and state clearly when it is not
  possible**. The second half is a UI obligation, not a fallback.
- **[T]** A job that cannot resume **says so** — `REQ-017`'s *"state clearly when resumption is not
  possible"* is the requirement, and **[T]** it uses the extractor's own words where there are any
  (`NFR-006`).
  **[T]** *(ruled `P-24`, `UX-007`)* That it says so **on its row** and offers *start again* as a distinct verb rather than
  silently restarting is the choice. The alternative — restarting transparently and saying so only
  in the log — is what most download managers do.
- **[T]** **Whether resume reintroduces a per-job pause is `T-113`'s to decide, and it must record
  the answer either way** (`UX-007`, 2026-08-07). *This file proposed that the queue-level drain
  stays, and was ruled against — not reversed, but deferred to the task that will have the
  evidence.* The answer depends on what resume actually costs per site and per format, which is
  what `T-113` is scheduled early to find out. Its record must say whether `JobStatus.PAUSED`
  returns and whether a playlist header gets `Pause all` (`T140-R5`). `UX-001` named `REQ-017` as
  its reopening **condition**, not its answer. **`UX-006` did not touch this**: that decision moved
  a queue-level default and left per-job control exactly where `UX-001` put it.

### 9.3 Duplicate-URL warning — `REQ-022`, built by `T-114`

- **[T]** `REQ-022`, as rescoped 2026-08-06: a URL already in the **queue** — or twice in one paste
  — is **confirmed, not refused**. Nothing is stored, and nothing is detected beyond the queue.
- **[T]** *(ruled `P-26`, `UX-007`)* The warning is a **staging row** state rather than a modal. `UX-003` puts *probe
  failures* in the dialog; it does not decide where a *duplicate* is reported (`T105-R3`). The
  argument is that a modal per duplicate in a paste of thirty is unusable — which is a good
  argument and still not an accepted rule.
- **[T]** *(ruled `P-27`, `UX-007`)* **Ordinary *Add to queue* is the override**, and the count includes the duplicates.
  `REQ-022` requires *an* override; it does not say that committing normally is it. The alternative
  — an explicit per-row *download anyway* — is a real option, and it is the one that makes the
  override a decision rather than an omission.
- **[T]** The duplication is **spoken**, not carried by a chip alone: `NFR-005` forbids information
  conveyed by colour alone, and a warning only sighted users receive is that rule broken.
  **[D]** It therefore joins the row's accessible text, which is where the row's other facts already
  are. **[D]** It needs no keyboard route of its own, because a row state is not a control.
- **[T]** *(`P-11`, **withdrawn** 2026-08-06 — never ruled, because the question stopped existing)*
  ~~The warning names **when** the URL was last downloaded and links to the History
  record.~~ **Withdrawn entirely, 2026-08-06.** `REQ-020` is gone and nothing records when anything
  was downloaded, so there is no date to name and no record to open. `REQ-022` is now a check
  against the **live queue**: the warning says the URL is already queued, and the row it is already
  on is right there to look at.

### Deliberately not offered

**[T]** *(ruled `P-28`, `UX-007`)* Both. `REQ-022` says *URL*, which bounds what must be detected without deciding what may
not be.

- **No detection by content.** Two URLs for the same video are not detectable without a heuristic
  nobody has specified.
- **No automatic skipping of duplicates in a paste.** `UX-003` refuses to drop a whole paste for a
  related reason — the user chose to paste them — but it does not decide this.

---

## 10 · The questions, and how each was ruled

**Every `[P]` clause in the original set was ratified by `UX-007` on 2026-08-07**, question by
question. The section is kept as the record of what was asked and answered rather than deleted,
because "what did we decide about the format table" is a question somebody will ask.

### Open — one question, added 2026-08-11

**Numbered `P-29` because `P-1`–`P-28` are all taken.** The first draft of this clause reused
`P-26`, which `UX-007` had already ratified as the duplicate-warning question in §9.3 — two
different questions and two different dispositions under one stable identifier, in the file whose
whole job is being the stable reference (`T222-R2`).

| # | Question | Status |
|---|---|---|
| **P-29** | **The options dialog is too tall for a short window. Which region gives up the height?** The four option groups scroll and the save line and buttons stay fixed. | **Ratified as built, 2026-08-13** (maintainer). Raised by `T-222`, recorded `[D]`, ruled `[P]` by the reviewer at `T222-R2`, and built on the reviewer's instruction that the demotion did not require unbuilding the correction — so the ruling was taken on a shape already in the tree. **The measured facts in §6 are what carried it**: the old layout clipped its own note at the opening size, and both floor-raising alternatives measured worse — one still cut the note, the other put *OK* off a 768px screen. What measurement could not decide was *which* region gives up the height, and that is the part now ruled. |

**§1's bar is no longer suspended for anything.** `P-29` is ratified, so the suspension it named has
ended. *(It read: no task may build a `[P]` clause until
it is ratified* held for all twenty-five of the original set; this one was built before it was
marked, which is the defect `T222-R2` names, and the reviewer chose to keep the correction rather
than revert it while the shape is decided.

**Three were ruled *against* what this file proposed**, and they are the rows worth reading:

| # | This file proposed | Ruled |
|---|---|---|
| **P-1** | The format table opens as a **modal dialog** | **The staging row, expanded.** A modal over a modal, when the list already has rows that open. `P-19` takes the same shape, so it is one mechanism |
| **P-10** | Resume **keeps** the queue-level drain | **`T-113` decides, and must record it either way.** The answer depends on what resume costs per site and format, which is what `T-113` exists to find out |
| **P-22** | The template preview is **unfocusable** read-only text | **A focusable read-only field.** This file stated the argument against itself — a user who cannot `Tab` to it cannot review it at their own pace — and that argument won |

**The other twenty-two were ratified as written.**

| # | Question | Ruled |
|---|---|---|
| P-2 | Video+audio: a mode, or two pickers? | A **mode** on one table |
| P-3 | Is the options editor reachable per-download? | **Yes**, and from the preset manager |
| P-4 | Does a one-off change offer *Save as preset…*? | **Yes, explicitly**; never silently |
| P-5 | Checkboxes per playlist entry? | **Checkboxes**, tri-state header |
| P-6 | One preset list or two? | **One**, built-ins marked |
| P-7 | Always exactly one default preset? | **Always one**; deleting promotes another |
| ~~P-8~~ | ~~Where do user presets persist?~~ | **Withdrawn** — `DAT-001` had decided it (`T105-R1`) |
| P-9 | Does the template editor list its fields? | **Inline**, beside the input |
| ~~P-11~~ | ~~Does the duplicate warning name the date?~~ | **Withdrawn 2026-08-06** — nothing records a date |
| P-12 | Do the five options get typed fields? | **Typed** — ruled by **`ARC-010`**, from above |
| P-13 | ffmpeg absent: what happens to merge? | **Hidden, with the reason in its place** |
| P-14 | Does the table refuse re-probe, download, filter? | **Refused** |
| P-15 | Does merging refuse three-way, external audio, auto-pairing? | **Refused** |
| P-16 | Do `T-109` and `T-111` share one screen? | **One screen**, reached two ways |
| P-17 | Is the subtitle control a multi-select? | **Yes, populated from the probe's own languages** |
| P-18 | Free post-processor field? Per-entry post-processing? | **Both refused** — the capability arrives via `REQ-031` |
| P-19 | Playlist picker: row or dialog? | **The staging row, opened** |
| P-20 | Preset manager: list beside a form, with buttons? | **Yes** |
| P-21 | Do presets refuse import/export and per-site rules? | **Refused** |
| P-23 | Containment failure at edit time or download time? | **Edit time, with the reason** |
| P-24 | Does a non-resumable job say so on its row? | **Yes**, with *start again* as its own verb |
| P-25 | Does the playlist picker refuse filtering? | **Refused** |
| P-26 | Duplicate warning: row state or modal? | **Row state** |
| P-27 | Is ordinary *Add to queue* the override? | **Yes** |
| P-28 | Does duplicate detection refuse content matching and auto-skip? | **Refused** |

### What the session was worth, and what it did not settle

**It moved eight deliverables from *startable* to *finishable*.** Each could always be begun —
nothing preceded them — and none could be completed, because completing one meant drawing a surface
this file had not settled. That distinction was invisible on the roadmap until 2026-08-07 and was
the phase's real blocker; no dependency ever was.

**Six were scope refusals and were ruled as one line** — `P-14`, `P-15`, `P-18`, `P-21`, `P-25`,
`P-28`. Each is a boundary of Phase 3's UI rather than a judgement that the feature is bad, which
is what keeps it cheap to revisit as its own task.

**Two rulings created new work rather than closing it:**

- **`P-10` gives `T-113` an acceptance criterion** — record whether per-job pause returns, whether
  `JobStatus.PAUSED` comes back, and whether a playlist header gets `Pause all` (`T140-R5`).
- **`P-17` answers a question this file never asked.** `SUBTITLE_LANGUAGES` is `("all",)` today, so
  *what the user picks from* was unspecified. The list comes from the probe's own languages, which
  means the control belongs beside a probed row — and a **preset** carrying languages a given video
  does not have is a case `T-109` must handle rather than assume away.

**A mockup is still worth building before `T-107` starts** — six of these were shape questions, and
`T-130`'s lesson is that a mockup and a window disagreed and nobody noticed. It would now be a check
on the ruling rather than the thing that produces it.

---

## 11 · The keyboard model, in one place

**[T]** `NFR-005`: full keyboard navigation, visible focus, screen-reader labels on all controls, and
**no information conveyed by colour alone**.

**[D]** Three rules this project has already paid to learn, and which every new surface inherits:

1. **A declared route works without a click first.** `T-152`: the `⋯` route did nothing until a
   pointer had selected a row, which is not a keyboard route. Every list opens with a **current**
   row — current, not selected, so per-row file actions still follow a real choice.
2. **A hidden widget is not in the keyboard order.** `T-060`: naming a widget the user cannot see is
   the defect. `focus_chain()` is per state, not per widget.
3. **The overflow holds everything the state permits when reached by keyboard**, and only what the
   row could not draw when reached by the `⋯` button (`T-135`). The two routes ask different
   questions and only the view knows which asked.

---

## 12 · What this application does not do, at any surface

Collected so a later task does not read an absence as an oversight — `T-105`'s third criterion.

**Marked like everything else** (`T105-R3`). The top group is settled and this file only restates
it; the bottom group is **this file proposing a limit**, and a refusal is as much a product choice
as an affordance — an absence nobody ratified is exactly what a later task would read as an
oversight.

### Settled — restated here, ruled elsewhere

| Not offered | Where it is decided |
|---|---|
| **[T]** Delete a file from disk | `UX-001`, `DAT-005` §2. Not as an option, not behind a checkbox. A record is not the downloads — and since 2026-08-06 the record is not visible either |
| **[T]** Per-job pause | `UX-001`, `T-080`. Queue-level drain only — reopening condition is `REQ-017`, which is `P-10` |
| **[T]** A detail pane, window or docked panel | `UX-005` §2. The row carries what a user needs |
| **[T]** A disabled control | `UX-005` §5, `T081-R3`. Absent instead, so the application never reports that it considered and declined |
| **[T]** Colour as the only carrier of state | `NFR-005`. The chip carries words |
| **[T]** A soft delete of history | `DAT-005` §4. No `deleted_at` column to protect a record whose loss costs little |
| **[T]** Any record of what has been downloaded | `REQ-020`, **withdrawn** 2026-08-06. Not a History tab, not a list, and not a private ledger behind one. A downloader is not a media library, and the ledger cost five review findings without a user ever seeing it |
| **[T]** Following a file after its queue row is cleared | `REQ-021`, amended 2026-08-06. The application does not claim to know where a file went |
| **[T]** Automatic pruning of records by age or size | `DAT-005` (2026-08-05), and `REQ-020` (2026-08-06) now states no automatic expiry outright |
| **[T]** Re-grouping history records that predate migration `0006` | `T-145`, approved |
| **[T]** A cookie path in History | `REQ-026`, `T159-R1`. History stores a `FormatChoice`, which cannot carry one |
| **[T]** A second persistence store for presets | `DAT-001`, `ARCHITECTURE.md` §5. TOML at `settings.toml` — see §8 |

### Proposed — limits this file is choosing, and none of them is ruled

| Not offered | Proposal | Argument |
|---|---|---|
| Re-probe, download-from, or filter the format table | `P-14` | `REQ-003` asks for sortable and is silent on the rest |
| Three-way merge, external audio, automatic pairing | `P-15` | `REQ-009`'s custom selector is the escape hatch |
| Arbitrary yt-dlp post-processors; per-entry post-processing | `P-18` | `REQ-010` names seven — but see `P-12`, since `post_processors` can express what the UI would refuse |
| Filtering a playlist picker by title or duration | `P-25` | A picker that hides entries can lie about *select all* |
| Preset import/export; per-site presets | `P-21` | `REQ-007` names five verbs and stops |
| Duplicate detection by content | `P-28` | `REQ-022` says *URL*, which is an argument about scope rather than a stated refusal |
| Automatic skipping of duplicates in a paste | `P-28` | `UX-003` refuses to drop a whole paste for a related reason; it does not decide this one |

---

## 13 · Which task builds which section

`T-105`'s fourth criterion is that Phase 3's tasks **reference** this file rather than duplicate it.
Each entry below carries a `Relevant context` pointer to its section.

| Section | Task | Requirement |
|---|---|---|
| §4 Format table | `T-107` | `REQ-003` |
| §5 Video + audio, merged | `T-108` | `REQ-008` |
| §6 Post-processing | `T-109` | `REQ-010` |
| §7 Playlist entry selection | `T-110` | `REQ-004` |
| §8 User presets | `T-111` | `REQ-007` |
| §9.1 Output template editor | `T-112` | `REQ-011` |
| §9.2 Resume | `T-113` | `REQ-017` |
| §9.3 Duplicate warning | `T-114` | `REQ-022` |
| §2, §3 The built window | — | Absorbed from `UX-003`, `UX-004`, `UX-005` |
