# UX_SPEC.md — Tracks & Trails

**Purpose:** What each surface shows, what it offers, and how a keyboard reaches it.
**Authority:** Canonical for the **built** surfaces below, which it absorbs from the `UX-` entries at
`DOC-002`'s trigger. **Not** authoritative for anything marked *Proposed* — those await a maintainer
ruling and are listed together in §10.
**Owner:** Planner
**Maintainer:** Sean Kottman
**Status:** Active — created 2026-08-06 for `T-105`, at the start of Phase 3
**Last updated:** 2026-08-07 — `UX-006` (the queue is stopped until started) and `ARC-010`
(option coverage), which between them amend §2, §2.1, §6 and two §10 rows
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
   anatomy is unchanged and now has one surface drawing it.)*
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

**[T]** `UX-005` (2026-08-04 amendment), `DAT-005` (2026-08-05 amendment) and `UX-006`
(2026-08-07). `+ Add URLs` first, as the primary action; the **run control**; `Clear finished`; and
the `Concurrent downloads` control that `ARC-007` put there until Phase 4's settings dialog
replaces it.

**[T]** **The run control is one control with two states, and the queue opens stopped** (`UX-006`).
It reads `Start` while the queue is stopped and `Stop` while it is running — the same single
checkable action `Pause queue` already was, renamed to what it now governs. *(It read `Pause queue`
until 2026-08-07, when the queue stopped running by default and "pause" became the wrong word for
the state a window opens in.)*

**[D]** **A stopped queue holding work says so where the work is.** Derived from `UX-005` §5 —
nothing is drawn that would be refused, and its converse, that a state which blocks a user's
expectation is stated — plus `NFR-005`'s rule against colour alone. A queue that shows `Held` rows
and nothing else is the one state in which a user can reasonably conclude the application is
broken. **`T-181` decides the treatment**; that there *is* one is not open.

**`Clear history` left the toolbar with the list it emptied** (2026-08-06), and nothing replaced it:
`REQ-020` was withdrawn the same day, so there is nothing anywhere to clear. `Clear finished` stays
— it clears completed **queue rows**, and with no records beside it there is nothing left for it to
be confused with. **There is no Settings menu**: the shell built to hold the records control went
with the control, and `T-146` brings it back with the settings `REQ-023` names.

**The rule the toolbar keeps:** nothing on it acts on a *selection*, and every verb on it names the
list it empties.

### 2.2 The state chip

**[T]** `UX-005` (2026-08-04). A chip on the title line carrying **words**, never colour alone
(`NFR-005`): `Done`, `Queued`, `62%`, `Failed`. *(This read "Queue tab only", against a History tab
whose every row was finished. There is one surface now and the rule is unchanged.)*

**[T]** A *group* header is the exception (`UX-005`, 2026-08-05): its chip is a **count** of the
members present — `16 items` — because a count is not a state. Never `14 of 16`. This was written
for History's groups and holds for the queue's, which are the ones that remain.

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

**[P-14]** All three. `REQ-003` asks for a sortable table and is silent on each of these, so they
are choices about scope rather than consequences of it.

- **No re-probe from the table.** What it shows is the probe the row already has. A refresh button
  implies the list goes stale within a session, and nothing establishes that it does.
- **No download from the table.** It chooses a format; committing is still the dialog's button.
- **No filtering or search.** A filter is a second interaction to learn for a list that is dozens of
  rows at worst.

---

## 5 · Choosing video + audio — `REQ-008`, built by `T-108`

`REQ-008`: *allow selecting specific format IDs directly from the format table, including a separate
video and audio stream to be merged.*

- **[P-2]** The table has two selection modes: **one format**, and **video + audio**. In the second,
  a row is chosen into whichever of the two slots its own kind matches, and the dialog shows the
  pair it will merge before it is committed.
- **[P-13]** `Merge` is offered only while ffmpeg is present. Absent, the mode is **not drawn**, and
  the reason is stated where the mode would have been. `UX-005` §5's never-draw-what-would-be-refused
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

**[D]** The mode is a control in the table's own frame, so it joins the `Tab` order ahead of the
header row — a mode that changes what `Enter` does must be reachable before the thing it changes.
`Space` switches mode; in **video + audio** the two chosen rows are announced as *"video: 137,
audio: 140"* rather than shown by highlight alone (`NFR-005`, no colour-only state).

### Deliberately not offered

**[P-15]** Both. `REQ-008` names *"a separate video and audio stream"*, which neither entails nor
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

**[P-16]** **That `T-109` and `T-111` therefore share one screen is a choice, not a consequence**
(`T105-R3`). What the data boundary establishes is that these options are preset-owned and that
`to_request()` refuses an override disagreeing with the preset the user was shown (`T015-R1`) — it
does not follow that one widget must edit both a saved preset and a one-off. The argument for
sharing is that a separate panel is a second place to set the same fields; the argument against is
that a per-download tweak and a stored preset have different save semantics, which `P-3` and `P-4`
are already circling. **Ruling on this decides whether `T-109` has a screen at all.**

**[P-12]** **Whether the five undedicated options get fields of their own is `T-109`'s first
question.** A `post_processors` list of opaque strings is what `Preset` has today; five booleans
would be typed, checkable and visible to `PRESET_OWNED_FIELDS`'s drift test, at the cost of widening
a model Phase 1 froze. This file does not decide it, and flags that a UI cannot be specified past
it: five checkboxes and one free list are different screens.

> **[T]** **Answered 2026-08-07 by `ARC-010`: typed.** The five get fields of their own, and the
> model widens. The decision took the question one level up — every option group faces it, not just
> post-processing — and ruled that a user-facing option is a typed, validated field, with one
> validated **escape hatch** (`REQ-031`) carrying what has no field yet. This clause stays because
> `T-109`'s screen has not been specified against the ruling yet; the question behind it is closed.

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
checkbox, arrow keys move within a combo, `Enter` commits, `Esc` cancels. **[T]** Every control
carries a screen-reader label (`NFR-005`).

**[P-17]** **The subtitle language control is a labelled multi-select** rather than a
comma-separated text field. `NFR-005` requires the control to be labelled and reachable; it does not
choose the widget, and `SUBTITLE_LANGUAGES` is `("all",)` today, so the set a user picks from is
itself unspecified.

### Deliberately not offered

**[P-18]** Both, and the first interacts with `P-12`: refusing a free-text post-processor field
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
- **[P-19]** The picker is the **staging list's own row**, opened, rather than a separate dialog.
  The supporting argument is that the queue and History already draw a playlist as one row that
  opens (`T-140`, `T-145`). It is **not** entailed by `UX-005` §3, whose one-anatomy rule is about
  the Queue and History tabs and says nothing about the add dialog (`T105-R3`).
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

**[T]** The first. **[P-25]** The second.

- **No reordering of entries.** `REQ-016`'s reordering predates grouping and does not say what it
  means inside one — `T-142`'s out-of-scope list already records this, so it is transcribed rather
  than chosen here.
- **No filtering by title or duration.** A picker that hides entries can lie about what *select all*
  did — which is an argument, not an authority. `REQ-004` is silent.

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

**[P-20]** **A list beside a form**, with create, duplicate and set-default as buttons in the
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

**[P-21]** Both. `REQ-007` names five verbs — create, edit, duplicate, delete, set default — and is
silent on the rest, so these are scope choices.

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
- **[T]** Path containment is **enforced**: no rendered template escapes the output directory.
  That is Phase 3's fourth exit criterion and `ARCHITECTURE.md` §8's rule, not a choice.
  **[P-23]** That the refusal is shown **at edit time, with the reason**, rather than at download
  time, is the choice — it is better feedback and it costs a validation path that runs on every
  keystroke.
- **[P-22]** **Keyboard path:** a single-line input with the preview below it as **read-only
  text**, not a second focus stop, updating as the field changes and announced on a pause rather
  than per keystroke. `NFR-005` requires the preview to be *available* to a screen reader; whether
  that means an unfocusable live region, a focusable read-only field, or an on-demand announcement
  is a real accessibility trade-off this file is not entitled to settle (`T105-R3`). A user who
  cannot `Tab` to the preview cannot review it at their own pace, which is the argument against the
  proposal above.
- **[P-9]** The editor lists the template fields it supports beside the input, rather than linking
  to yt-dlp's documentation, because the set this application supports is not yt-dlp's whole set.

### 9.2 Resume across a restart — `REQ-017`, built by `T-113`

- **[T]** `REQ-017`: resume where the site and format allow it, **and state clearly when it is not
  possible**. The second half is a UI obligation, not a fallback.
- **[T]** A job that cannot resume **says so** — `REQ-017`'s *"state clearly when resumption is not
  possible"* is the requirement, and **[T]** it uses the extractor's own words where there are any
  (`NFR-006`).
  **[P-24]** That it says so **on its row** and offers *start again* as a distinct verb rather than
  silently restarting is the choice. The alternative — restarting transparently and saying so only
  in the log — is what most download managers do.
- **[P-10]** **Resume does not reintroduce a per-job pause.** `UX-001` made pause a queue-level
  drain and `T-080` deleted `JobStatus.PAUSED` outright; `UX-001` names `REQ-017` as the condition
  under which those edges may be wanted back, so this is the moment that question is live.
  **This file proposes that it stays a queue-level drain and that `Pause all` on a playlist header
  stays deferred** — but it is `UX-001`'s to reopen, and `T140-R5` already deferred the group verb
  to exactly this decision.

### 9.3 Duplicate-URL warning — `REQ-022`, built by `T-114`

- **[T]** `REQ-022`, as rescoped 2026-08-06: a URL already in the **queue** — or twice in one paste
  — is **confirmed, not refused**. Nothing is stored, and nothing is detected beyond the queue.
- **[P-26]** The warning is a **staging row** state rather than a modal. `UX-003` puts *probe
  failures* in the dialog; it does not decide where a *duplicate* is reported (`T105-R3`). The
  argument is that a modal per duplicate in a paste of thirty is unusable — which is a good
  argument and still not an accepted rule.
- **[P-27]** **Ordinary *Add to queue* is the override**, and the count includes the duplicates.
  `REQ-022` requires *an* override; it does not say that committing normally is it. The alternative
  — an explicit per-row *download anyway* — is a real option, and it is the one that makes the
  override a decision rather than an omission.
- **[T]** The duplication is **spoken**, not carried by a chip alone: `NFR-005` forbids information
  conveyed by colour alone, and a warning only sighted users receive is that rule broken.
  **[D]** It therefore joins the row's accessible text, which is where the row's other facts already
  are. **[D]** It needs no keyboard route of its own, because a row state is not a control.
- **[P-11]** ~~The warning names **when** the URL was last downloaded and links to the History
  record.~~ **Withdrawn entirely, 2026-08-06.** `REQ-020` is gone and nothing records when anything
  was downloaded, so there is no date to name and no record to open. `REQ-022` is now a check
  against the **live queue**: the warning says the URL is already queued, and the row it is already
  on is right there to look at.

### Deliberately not offered

**[P-28]** Both. `REQ-022` says *URL*, which bounds what must be detected without deciding what may
not be.

- **No detection by content.** Two URLs for the same video are not detectable without a heuristic
  nobody has specified.
- **No automatic skipping of duplicates in a paste.** `UX-003` refuses to drop a whole paste for a
  related reason — the user chose to paste them — but it does not decide this.

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
| ~~P-8~~ | ~~Where do user presets persist?~~ **Withdrawn — already decided** (`T105-R1`). `DAT-001` and `ARCHITECTURE.md` §5 fix it: TOML, at `user_config_dir/tracksandtrails/settings.toml`. Transcribed in §8; the number is kept so the withdrawal is legible rather than silent | §8 | — |
| P-9 | Does the template editor list supported fields inline? | §9.1 | Scope of `T-112` |
| P-10 | **Does `REQ-017` reopen per-job pause?** `UX-001` names this as its reopening condition | §9.2 | **Reopens `UX-001` and `T-080`.** Also decides `Pause all` on a group, deferred by `T140-R5` |
| P-11 | ~~Does the duplicate warning name the date?~~ **Withdrawn 2026-08-06** — nothing records a date | §9.3 | — |
| P-12 | ~~**Do remux, recode, embed-thumbnail, embed-metadata and embed-chapters get typed fields on `Preset`**, or stay strings in `post_processors`?~~ **Ruled 2026-08-07 — typed** (`ARC-010`) | §6 | The model widens, as this said it would. `T-109`'s screen is now specified *against* the ruling rather than blocked by the question |
| P-13 | When ffmpeg is absent, is the merge mode hidden, shown-and-refused, or the table drawn without it? | §5 | `UX-005` §5 requires *some* treatment, not this one |
| P-14 | Does the format table refuse re-probe, download-from-table, and filtering? | §4, §12 | Scope of `T-107` |
| P-15 | Does merging refuse three-way, external audio and automatic pairing? | §5, §12 | Scope of `T-108` |
| P-16 | **Do `T-109` and `T-111` share one screen?** The data boundary does not decide it | §6 | **Decides whether `T-109` has a screen of its own at all** |
| P-17 | Is the subtitle language control a multi-select? | §6 | `SUBTITLE_LANGUAGES` is `("all",)` today, so the set is unspecified too |
| P-18 | Does the editor refuse a free post-processor field and per-entry post-processing? **Half-ruled 2026-08-07** (`ARC-010`) | §6, §12 | The post-processor list stays refused; the capability is reachable through `REQ-031`'s validated field. Per-entry post-processing is still open, under `T-110` |
| P-19 | Is the playlist picker the staging row opened, or a dialog? | §7 | Not entailed by `UX-005` §3, which is about the two tabs |
| P-20 | Is the preset manager a list beside a form, with buttons rather than a menu? | §8 | `T118-R5` forbids dropping a control, not this layout |
| P-21 | Do presets refuse import/export and per-site rules? | §8, §12 | Scope of `T-111` |
| P-22 | **Is the template preview an unfocusable live region, a focusable read-only field, or announced on demand?** | §9.1 | A real accessibility trade-off — a user who cannot `Tab` to it cannot review it at their own pace |
| P-23 | Is a containment failure shown at edit time rather than at download time? | §9.1 | Enforcement is required; *when it is surfaced* is the choice. **`T-112` already carries the same proposal as an acceptance criterion** — one ruling settles both, and they must not be answered separately |
| P-24 | Does a non-resumable job say so on its row and offer *start again* as its own verb? | §9.2 | The alternative is restarting transparently |
| P-25 | Does the playlist picker refuse filtering? | §7, §12 | Scope of `T-110` |
| P-26 | Is the duplicate warning a row state rather than a modal? | §9.3 | `UX-003` places *probe failures*, not this |
| P-27 | **Is ordinary *Add to queue* the override**, or is an explicit per-row *download anyway* wanted? | §9.3 | `REQ-022` requires an override; it does not say which |
| P-28 | Does duplicate detection refuse content matching and automatic skipping? | §9.3, §12 | Scope of `T-114` |

### Reading this list

**It grew from twelve to twenty-seven under review, and that is the correction working.** `T105-R3`
found that several real choices had been presented as *derived* and that every refusal was unmarked
— so the first count was not a measure of how much was open, it was a measure of how much had been
marked. Nothing was added to the design; the marks caught up with it.

**Four decide more than a layout, and one of the four has since been ruled on:**

- **`P-10`** reopens `UX-001` and `T-080` by design, and is the phase's highest uncertainty (`T-113`).
  *(`UX-006` did **not** answer it. That decision moved the queue-level gate's default; per-job
  control is untouched and still arrives with resume.)*
- **`P-12`** widens a model frozen since Phase 1, and decides what `T-109`'s screen contains.
  **Ruled 2026-08-07 by `ARC-010`: typed, and the model widens.** It was ruled from above rather
  than answered in place — every option group faces the same question, and `REQ-030`/`REQ-031` are
  the general answer.
- **`P-16`** decides whether `T-109` has a screen of its own at all.
- **`P-22`** is an accessibility trade-off rather than a preference, and `NFR-005` does not settle it.

**Twelve are scope refusals** — `P-14`, `P-15`, `P-18`, `P-21`, `P-25`, `P-28` and their siblings in
§12 — and they can sensibly be ruled as a group: *this is the boundary of Phase 3's UI.*

**The rest are where a surface lives and what shape it is** — `P-1`, `P-2`, `P-5`, `P-6`, `P-19`,
`P-20`. Those are the ones a **mockup** would answer faster than this table can, which is `T-130`'s
lesson: that finding exists because a mockup and the window disagreed and nobody noticed. Ratifying
them from prose alone is the weakest part of this document.

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
