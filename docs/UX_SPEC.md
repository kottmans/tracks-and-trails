# UX_SPEC.md — Tracks & Trails

**Purpose:** What each surface shows, what it offers, and how a keyboard reaches it.
**Authority:** Canonical for the **built** surfaces below, which it absorbs from the `UX-` entries at
`DOC-002`'s trigger. **Not** authoritative for anything marked *Proposed* — those await a maintainer
ruling and are listed together in §10.
**Owner:** Planner
**Maintainer:** Sean Kottman
**Status:** Active — created 2026-08-06 for `T-105`, at the start of Phase 3
**Last updated:** 2026-08-06
**Update when:** A surface changes, a `UX-` entry is accepted or amended, or a §10 question is ruled on.
**Does not contain:** Why a decision was made (`ai/DECISIONS.md`), what must be tested
(`ai/TESTING.md`), the visual palette (`ARCHITECTURE.md` §8), or Phase 4's settings dialog
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
- **`ai/DECISIONS.md` states why, and what was rejected.** A `UX-` entry accepted *after* this file
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
| **[P]** *Proposed* | **A product choice nobody has made.** Written so it can be ruled on, not so it can be built. Every one is collected in §10, and **no task may build a [P] clause until it is ratified.** |

---

## 2 · The window, as built

**[T]** `UX-005`. Two tabs over one list, no detail pane, every verb on the row.

1. **`Queue` and `History` are tabs**, each showing a count. Not a splitter, not one above the other.
2. **There is no detail pane.** Selecting a row opens nothing. A row shows what a user needs to know
   about that job.
3. **Both tabs draw the same row anatomy** — thumbnail, title, uploader and duration, progress and
   state. History changes what the fields *say*, not what they are: where the queue shows progress
   and speed, History shows the saved path, the size and when.
4. **Every verb the row's state permits is on its last line**, right-aligned, sharing that line with
   the format control, plus `⋯` for the rest — which is also the keyboard route.
5. **Nothing is drawn disabled and nothing is drawn that would be refused.** A row offers what its
   state permits and says nothing about the rest.
6. **The per-row format control appears only while `retarget()` would accept it**; it is plain text
   once a download starts.
7. **There is no per-job pause.** `pause()` is queue-wide, in-flight sessions finish, and a waiting
   row reads **Held**, never *Paused*.
8. **A finished download stays in the Queue tab** with *Open* and *Show in folder* until
   *Clear finished* moves it on.
9. **History removal is selection-scoped**, its verb names its own count, and *"files are never
   deleted"* sits in the status bar while History is showing.

### 2.1 The toolbar

**[T]** `UX-005` (2026-08-04 amendment) and `DAT-005` (2026-08-05 amendment).
`+ Add URLs` first, as the primary action; `Pause queue`; `Clear finished`; `Clear history`; and the
`Concurrent downloads` control that `ARC-007` put there until Phase 4's settings dialog replaces it.

**The rule the toolbar keeps:** nothing on it acts on a *selection*, and every verb on it names the
list it empties. That is what makes each unambiguous with two tabs in the window.

### 2.2 The state chip

**[T]** `UX-005` (2026-08-04). A chip on the title line carrying **words**, never colour alone
(`NFR-005`): `Done`, `Queued`, `62%`, `Failed`. **Queue tab only** — every History row is finished,
so a chip reading *Done* on all of them is noise.

**[T]** A History *group* header is the exception (`UX-005`, 2026-08-05): its chip is a **count** of
the members present — `16 items` — because a count is not a state. Never `14 of 16`.

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
- **[T]** `UX-004`: Retry and Remove are a context menu, reachable by the Menu key and Shift+F10 as
  well as by pointer.

---

## 4 · The format table — `REQ-003`, built by `T-107`

`REQ-003`: *show the available formats for a probed URL in a sortable table (format ID, extension,
resolution, fps, codecs, bitrate, filesize/estimate, notes).*

### Where it lives

**[P-1]** The table opens from the **format control** — the same *Download as* control `UX-004` put
on every staging row and `UX-005` §6 puts on every retargetable queue row — through an entry reading
**`Choose specific formats…`** below the preset list.

*Why it is [P] and not [D]:* `UX-005` §2 forbids a detail pane, which rules out the obvious home and
leaves the choice between a modal dialog, a sheet over the window, and an expanding row. This
proposes the first. Nothing accepted decides it.

### What it shows

- **[T]** One row per format, with every column `REQ-003` names: format ID, extension, resolution,
  fps, codecs, bitrate, filesize or estimate, notes.
- **[T]** Sortable. **[D]** Sorting is over the **projection**, not the display string: `1080p` sorts
  after `720p` and `144p`, and `~12.4 MB` sorts as a number. Derived from `T-075`, which is the
  defect of a table sorting its own text.
- **[D]** A format missing a field renders the placeholder the rest of the window already uses
  (`UNKNOWN_TEXT`), never an empty cell and never `None`. Derived from `_text_or_absent`'s rule.
- **[D]** The table reads a `FormatInfo` projection, never raw `info_dict` keys. Derived from
  `NFR-008` and `ARCHITECTURE.md`'s declared-fields-only rule.

### Keyboard path — `NFR-005`

**[D]** Throughout, derived from `NFR-005` and the routes `T-124`/`T-152` already established.

| Key | Does |
|---|---|
| `Enter` / `Space` on the control's `Choose specific formats…` | Opens the table |
| `Tab` | Moves between the header row, the table body and the buttons |
| `↑` `↓` | Move the current format |
| `Space` on a header | Sorts by that column; again reverses |
| `Enter` | Chooses the current format and closes |
| `Esc` | Closes, choosing nothing |

The table opens with a **current row** already set, because a declared keyboard route that needs a
click first is not one (`T-152`).

### Deliberately not offered

- **No re-probe from the table.** What it shows is the probe the row already has. A refresh button
  implies the list goes stale within a session, and nothing establishes that it does.
- **No download from the table.** It chooses a format; committing is still the dialog's button.
- **No filtering or search.** `REQ-003` asks for sortable, and a filter is a second interaction to
  learn for a list that is dozens of rows at worst.

---

## 5 · Choosing video + audio — `REQ-008`, built by `T-108`

`REQ-008`: *allow selecting specific format IDs directly from the format table, including a separate
video and audio stream to be merged.*

- **[P-2]** The table has two selection modes: **one format**, and **video + audio**. In the second,
  a row is chosen into whichever of the two slots its own kind matches, and the dialog shows the
  pair it will merge before it is committed.
- **[D]** `Merge` is offered only while ffmpeg is present. Absent, the mode is **not drawn**, and
  the reason is stated where the mode would have been — `UX-005` §5 forbids drawing what would be
  refused, and `REQ-024` owns the detection. **[D]** The ffmpeg check reads the **resulting
  selector**, not the chosen format, which is `T-061`'s finding exactly.
- **[D]** Choosing a pair writes one request whose selector is the two ids joined. What the row then
  *says* is the shared naming rule's answer (`ui/format_text.py`), not the raw selector — which is
  `T140-R3`, `T126-R2` and `T-159`, all three of which were this same defect.

### Keyboard path

**[D]** The mode is a control in the table's own frame, so it joins the `Tab` order ahead of the
header row — a mode that changes what `Enter` does must be reachable before the thing it changes.
`Space` switches mode; in **video + audio** the two chosen rows are announced as *"video: 137,
audio: 140"* rather than shown by highlight alone (`NFR-005`, no colour-only state).

### Deliberately not offered

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

So `REQ-010`'s surface is **the preset editor's**, not a new panel of its own, and `T-109` and
`T-111` share one screen rather than building two. A separate post-processing panel would be a
second place to set the same fields, and `to_request()` already refuses an override that disagrees
with the preset the user was shown (`T015-R1`).

**[P-12]** **Whether the five undedicated options get fields of their own is `T-109`'s first
question.** A `post_processors` list of opaque strings is what `Preset` has today; five booleans
would be typed, checkable and visible to `PRESET_OWNED_FIELDS`'s drift test, at the cost of widening
a model Phase 1 froze. This file does not decide it, and flags that a UI cannot be specified past
it: five checkboxes and one free list are different screens.

- **[P-3]** The editor is reachable **two ways**: as *"Options…"* on the format control, editing a
  one-off choice for this download only; and from the preset manager (§8), editing a saved preset.
  The same widget in both, with a different title and a different save action.
- **[D]** Audio quality is offered only for a codec where a bitrate means something — `MP3_BITRATES`
  is MP3's scale, and `with_audio_quality` already refuses any other codec for that reason
  (`T076-R1`).
- **[P-4]** A one-off options change **does not** silently become a preset. The editor offers
  *"Save as preset…"* explicitly.

### Keyboard path

**[D]** A form, so the platform's own order applies: `Tab` between fields, `Space` toggles a
checkbox, arrow keys move within a combo, `Enter` commits, `Esc` cancels. **Every control carries a
screen-reader label** (`NFR-005`), and the subtitle language list is a labelled multi-select rather
than a comma-separated text field, because a text field would need its syntax explained.

### Deliberately not offered

- **No arbitrary yt-dlp post-processor list.** `REQ-010` names seven; a free-text postprocessor
  field would be an unbounded surface with no way to say what it will do.
- **No per-entry post-processing inside a playlist.** The playlist's entries share their group's
  format (`UX-005` row 9c), and splitting that per entry is a decision nobody has asked for.

---

## 7 · Playlist entry selection — `REQ-004`, built by `T-110`

`REQ-004`: *for a playlist, let the user select which entries to enqueue, including select-all and
range selection, before any download starts.*

- **[T]** `UX-003`'s consequence: *"Phase 3's playlist picker gets its prerequisite for free"* — a
  playlist expands into entries only after a probe, which `UX-003` guarantees has happened by the
  time a row exists.
- **[D]** The picker is the **staging list's own row**, opened, not a separate dialog: the queue and
  History already draw a playlist as one row that opens (`T-140`, `T-145`), and a third way to show
  the same shape is the drift `UX-005` §3 exists to prevent.
- **[P-5]** Each entry carries a **checkbox**, and the group header carries a tri-state checkbox
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

- **No reordering of entries.** `REQ-016`'s reordering predates grouping and does not say what it
  means inside one (`T-142`'s out-of-scope list already records this).
- **No filtering by title or duration.** Not asked for, and a picker that hides entries is a picker
  that can lie about what *select all* did.

---

## 8 · User presets — `REQ-007`, built by `T-111`

`REQ-007`: *create, edit, duplicate, delete, set one as default.*

- **[P-6]** A **preset manager**, reached from the format control's `Manage presets…` and listing
  built-ins and the user's own together, with the built-ins not deletable and marked as such.
- **[D]** A built-in cannot be edited in place. `custom_preset` and `with_audio_quality` already
  derive a new preset rather than mutating one, because a request that disagrees with the preset the
  user was shown defeats `REQ-009`. Editing a built-in therefore **duplicates it first**, visibly.
- **[P-7]** The default preset is what a new paste inherits. One default, always set; clearing it is
  not offered, because the dialog needs *something* to inherit.

### Keyboard path

**[D]** A list beside a form. `Tab` moves between them; `↑` `↓` choose a preset; `Enter` edits the
current one; `Delete` removes a user preset and does nothing on a built-in, which is **not** drawn
as a disabled control (`UX-005` §5) — the built-in is simply marked as one. Creating, duplicating and
setting the default are buttons in the list's own `Tab` order, not a context menu, because `T118-R5`
established that a menu-only route is not authority to drop a visible control.

### Open, and deliberately not answered here

**[P-8]** **Where user presets persist is a `DAT-` decision, not this file's.** `DAT-001` chose
SQLite for durable state and `ARC-007` put Phase 2's settings in `settings.toml`; presets are
arguably either. `T-111` records the same gap as *"persisted state, and where it lives needs a
decision"*. **No task should choose this in passing.**

### Deliberately not offered

- **No import or export of presets.** A sharing format is a compatibility commitment.
- **No per-site presets.** Nothing asks for it, and it would need a matching rule nobody has specified.

---

## 9 · The rest of Phase 3

### 9.1 Output template editor — `REQ-011`, built by `T-112`

- **[T]** `REQ-011` as amended (2026-08-01, `T046-R2` and `T046-R4`): a live preview of the resulting
  path, **labelled as the *intended* path** wherever the final container is yt-dlp's to choose.
  Audio extraction to a **named** codec previews exactly, through yt-dlp's own `ACODECS` table — the
  codec is not the extension, since `aac` and `alac` both land in `m4a`.
- **[T]** *Audio only (original)* is **provisional** and says so: `best` keeps the codec rather than
  the container, and yt-dlp decides by running `ffprobe` on the downloaded file.
- **[D]** Preview and the real write are **one function**. Two would drift, which is the whole of
  `T-046`'s finding.
- **[D]** Path containment is shown, not just enforced: a template that would escape the output
  directory is refused **with the reason**, at edit time rather than at download time.
- **[D]** **Keyboard path:** a single-line input with the preview below it as **read-only text**,
  not a second focus stop — a preview a `Tab` lands on reads as something to edit. The preview
  updates as the field changes and is announced on a pause rather than per keystroke, so a screen
  reader is not narrating every character (`NFR-005`).
- **[P-9]** The editor lists the template fields it supports beside the input, rather than linking
  to yt-dlp's documentation, because the set this application supports is not yt-dlp's whole set.

### 9.2 Resume across a restart — `REQ-017`, built by `T-113`

- **[T]** `REQ-017`: resume where the site and format allow it, **and state clearly when it is not
  possible**. The second half is a UI obligation, not a fallback.
- **[D]** A job that cannot resume says so **on its row**, in the extractor's own words where there
  are any (`NFR-006`), and offers to start again rather than silently restarting.
- **[P-10]** **Resume does not reintroduce a per-job pause.** `UX-001` made pause a queue-level
  drain and `T-080` deleted `JobStatus.PAUSED` outright; `UX-001` names `REQ-017` as the condition
  under which those edges may be wanted back, so this is the moment that question is live.
  **This file proposes that it stays a queue-level drain and that `Pause all` on a playlist header
  stays deferred** — but it is `UX-001`'s to reopen, and `T140-R5` already deferred the group verb
  to exactly this decision.

### 9.3 Duplicate-URL warning — `REQ-022`, built by `T-114`

- **[T]** `REQ-022`: detect that a URL has been downloaded before and warn before re-downloading,
  **with an override**.
- **[D]** The warning is a **staging row** state, not a modal: `UX-003` makes the dialog the place
  where a URL's problems are shown, and a modal per duplicate in a paste of thirty is unusable.
- **[D]** It never blocks. The override is the row committing anyway, and the count on *Add to
  queue* includes it.
- **[D]** **Keyboard path:** the warning is a row state, so it needs no route of its own — the row
  is already in the list's order and the override is committing. What it does need is to be
  **spoken**: the row's accessible text names the duplication, because a warning carried only by a
  chip is a warning only sighted users have.
- **[P-11]** The warning names **when** the URL was last downloaded and links to the History record,
  because *"you have had this before"* without a date is not enough to act on.

### Deliberately not offered

- **No detection by content.** Two URLs for the same video are not detectable without a heuristic
  nobody has specified, and `REQ-022` says *URL*.
- **No automatic skipping of duplicates in a paste**, for the same reason `UX-003` refuses to drop
  a whole paste: the user chose to paste them.

---

## 10 · Open questions — every [P] clause, collected

**Nothing in this section may be built until it is ruled on.** They are gathered here so a ruling is
one pass rather than eleven, and so a task cannot mistake a proposal for a decision — which is
`T145-R1` and `T144-R1`'s lesson, applied before the fact this time rather than after.

| # | Question | Where | Costs, if the answer differs |
|---|---|---|---|
| P-1 | Does the format table open as a modal dialog, a sheet, or an expanding row? | §4 | Layout only; `T-107`'s content is unaffected |
| P-2 | Is video+audio a **mode** on the table, or two separate pickers? | §5 | `T-108`'s interaction, not its selector |
| P-3 | Is the post-processing editor reachable as a per-download *Options…* as well as from the preset manager? | §6 | If not, every option change becomes a saved preset |
| P-4 | Does a one-off options change offer *Save as preset…*? | §6 | Small; follows P-3 |
| P-5 | Checkboxes per playlist entry, with a tri-state group header? | §7 | The alternative is selection-as-checked, which collides with `ExtendedSelection` |
| P-6 | A preset manager listing built-ins and user presets together? | §8 | Two lists is the alternative |
| P-7 | Is there always exactly one default preset? | §8 | "No default" needs an inherit rule for the dialog |
| P-8 | **Where do user presets persist** — SQLite (`DAT-001`) or `settings.toml` (`ARC-007`)? | §8 | **A `DAT-` entry.** Changing it later is a migration |
| P-9 | Does the template editor list supported fields inline? | §9.1 | Scope of `T-112` |
| P-10 | **Does `REQ-017` reopen per-job pause?** `UX-001` names this as its reopening condition | §9.2 | **Reopens `UX-001` and `T-080`.** Also decides `Pause all` on a group, deferred by `T140-R5` |
| P-11 | Does the duplicate warning name the date and link to the History record? | §9.3 | Small; `T-114` is the smallest item in the phase |
| P-12 | **Do remux, recode, embed-thumbnail, embed-metadata and embed-chapters get typed fields on `Preset`**, or stay strings in `post_processors`? | §6 | **Widens a Phase 1 model.** Five checkboxes and one free-text list are different screens, so `T-109` cannot be specified past it |

**P-8, P-10 and P-12 are the three that are not about layout.** P-8 is a data decision a later
migration would have to undo; P-10 reopens two accepted decisions by design and is the phase's
highest uncertainty (`T-113`); P-12 widens a model that has been frozen since Phase 1 and decides
what `T-109`'s screen even is.

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

| Not offered | Why, and where it is recorded |
|---|---|
| Delete a file from disk | `UX-001`, `DAT-005` §2. Not as an option, not behind a checkbox. History is a record, not the downloads |
| Per-job pause | `UX-001`, `T-080`. Queue-level drain only — reopening condition is `REQ-017` (P-10) |
| A detail pane, window or docked panel | `UX-005` §2. The row carries what a user needs |
| A disabled control | `UX-005` §5, `T081-R3`. Absent instead, so the application never reports that it considered and declined |
| Colour as the only carrier of state | `NFR-005`. The chip carries words |
| A soft delete of history | `DAT-005` §4. No `deleted_at` column to protect a record whose loss costs little |
| Automatic pruning of history by age or size | `DAT-005` (2026-08-05). A policy nobody has decided |
| Re-grouping history records that predate migration `0006` | `T-145`. Their membership was never written down, and inferring it presents a guess as a record |
| A cookie path in History | `REQ-026`, `T159-R1`. History stores a `FormatChoice`, which cannot carry one |
| Arbitrary yt-dlp post-processors | §6. `REQ-010` names seven |
| Preset import/export, per-site presets | §8 |
| Duplicate detection by content | §9.3. `REQ-022` says *URL* |

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
