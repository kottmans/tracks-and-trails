# TASKS.md — Tracks & Trails

**Purpose:** Unfinished work: review, ready, proposed and blocked tasks.
**Owner:** Planner (priorities); Implementer (task/status); Reviewer (review disposition)
**Last updated:** 2026-09-08
**Update when:** Work starts, changes scope/status, closes or reopens.

Statuses: Proposed · Ready · In Progress · Blocked · In Review · Complete · Cancelled.
Complete and Cancelled records live in [COMPLETED_TASKS](COMPLETED_TASKS.md).
Move each record there in the same update that closes it; keep no closed-task
stubs here. Preserve IDs, evidence, limitations and follow-up routes. Check both
files before allocating an ID; IDs are never reused. Task-reading tests and
the placement gate read both files. Current phase and blockers are in [STATUS](STATUS.md).

## In Review

### T-308 — The startup warning opens behind the window it blocks

**Status:** In Review — **changes requested 2026-09-09, corrected the same day; awaiting
re-review.** The problem is **carried** on `Composition`; `run()` calls `present()`, which shows
the window and then reports.

#### Correction round 2, 2026-09-09

- **`T308-R3` (High, blocking) — corrected. It was a regression I introduced in the correction.**
  The probe replaced `XDG_CONFIG_HOME` but used `setdefault` for the data and cache roots, so an
  inherited `XDG_DATA_HOME` survived while the tool advertised isolation — and `compose()` opens
  that database and runs `recover_interrupted()` before any window appears. A reviewer's canary
  went `RUNNING` → `FAILED / INTERRUPTED`, **exit code 0**. It now sets all four XDG roots
  unconditionally, resolves and prints `database_path()` and `cache_directory()`, and **refuses to
  compose** if either lands outside the temporary profile.
  `test_the_stacking_probe_cannot_reach_an_inherited_profile` keeps the reviewer's reproduction.
  **Removing `setdefault` alone does not fail it — the refusal catches that first** — so the
  mutation removes both layers, and then it does.
  On the machine that produced the original measurements the defect did not fire: both variables
  were unset and the real database's mtime is 2026-09-03, six days earlier. **That is luck about
  one environment, not a property of the tool.**
- **`T308-R1` (Medium) — the visual half is now observed; the input half is not.** The composited
  desktop was photographed on Wayland and again under `xcb`, and read: on **both** platforms the
  warning is drawn **over** the main window, centred in its visible rectangle, with its own
  titlebar and `OK`, and the window visible around it rather than hidden. The rendered text is the
  corrected `T-309` wording, so that correction is confirmed as drawn and not merely composed.
  **This supersedes the first amendment's "position relative to the parent is not established"** —
  it came from comparing two coordinate spaces that are not comparable, and a photograph does not
  have that problem.
  **The images are not committed**: they are full-desktop captures containing unrelated windows,
  and this repository is public.
  **Normal input is now observed on X11.** `xdotool` was installed at the maintainer's hand, so
  events come from the X server rather than from inside the client: a real `Return` left
  `--onlyvisible` listing only the main window, and a real pointer click then opened `+ Add URLs`
  fully rendered. All three clauses — above its parent, dismissible, window usable afterwards —
  are observed there.
  **Wayland was observed by the maintainer**, running it himself against a throwaway profile:
  visible above the window, dismissed by `OK`/`Return`, window responsive afterwards — yes to all
  three clauses. Recorded as his observation rather than a measurement, which is what a criterion
  about what *a person* sees requires. **`T308-R1`'s clauses are therefore observed on both
  platforms**, synthetically on X11 and by a person on Wayland.
  `ydotool` was installed and removed again: its socket is root-only while its client looks
  elsewhere, and bridging that means a world-writable input-injection socket on a machine whose
  repository is public. Not done, and not needed.
- **`T308-R2` — resolved at `10e079c`** by the reviewer.

#### Correction round, 2026-09-09

- **`T308-R1` (Medium, blocking) — the required checks were run.**
  [Both platforms recorded](evidence/2026-09-09-T308-warning-stacking.md): on Wayland and on X11
  the dialog is exposed, active, `WindowModal`, a **transient of the window**, centred in its
  rectangle, dismissible by its own `OK`, and the window is enabled afterwards. **Stacking order
  itself is not read and cannot be from inside a Wayland client**, and whether a person *finds* it
  is perceptual — both are stated as unestablished rather than implied. KDE only.
- **`T308-R2` (Low) — corrected, and the finding was right.** The guards called the reporting
  themselves, so deleting the production branch passed all seven. `run()`'s inline sequence is now
  `app.present()`, extracted because `run()` builds its own `QApplication` and cannot be called
  from a test session. A test drives `present()` and records **whether the window was visible at
  the moment of reporting**: removing the report fails it, and moving it before `show()` fails it.
  Both mutations the finding names are now killed. **`run()`'s one-line call to `present()` is
  still uncovered**, and the function's docstring says so.

**Stacking itself is not asserted and cannot be, offscreen.** The guards check that `compose()`
opens nothing, and that after `show()` the box is visible and a child of the window — which is
what gives the compositor a parent to keep it above. **The real-display check on Wayland and X11
is still outstanding**, and `T-288` is why that distinction is written down rather than assumed.
notification appears behind the main menu, which is completely inaccessible while this notification
is up."*
**Owner:** Implementer
**Priority:** **High** — the application is unusable until a dialog the user may not be able to
find is dismissed. It fires on every launch for anyone whose settings name a folder that has since
gone, which is the maintainer's current state
**Phase:** Phase 4
**Depends on:** nothing
**Relevant context:** `ARC-008`; `T-102`; `main_window.report_settings_problem`
**Affected surfaces:** `src/tracks_and_trails/app.py`'s startup order
**Risk:** Low to fix; the ordering is two lines apart
**Required checks:** `pytest tests/ui tests/integration`; a real launch with a settings file naming
a missing download folder, on Wayland and on X11

#### The cause, located

| Where | What happens |
|---|---|
| `app.py:1190`, inside `compose()` | `window.report_settings_problem(...)` — `QMessageBox(self)`, then `box.open()` |
| `app.py:262`, after `compose()` returns | `composition.window.show()` |

**The dialog is opened before its parent is ever shown.** `open()` makes it window-modal, so it
blocks the main window — and because the parent is mapped *afterwards*, the compositor puts the
main window on top of a dialog that was never a visible transient child. The result is a modal
nobody can see blocking a window nobody can use.

#### Acceptance criteria

- The warning is opened **after** the window it is parented to is shown, and appears above it.
- **Asserted, not eyeballed.** A test that shows the window, reports a problem, and checks the
  box is a visible transient of the window rather than merely constructed.
- Checked on a real display on Wayland **and** X11: stacking is the compositor's, and this project
  has already been caught once by a Wayland-only behaviour (`T-288`).
- The existing reason for `open()` over `exec()` is preserved — `exec()` blocks the event loop in
  a test with nothing to dismiss it.

#### Out of scope

- What the dialog says, which is `T-309`.

### T-309 — The settings warning claims a read failure that did not happen

**Status:** In Review — **changes requested 2026-09-09, corrected the same day; awaiting
re-review.**

#### Correction round, 2026-09-09

- **`T309-R1` (Medium, blocking) — corrected.** The readable-file headline said *"their defaults
  are in use"* over values that were **clamped**: `rate_limit_bytes = 1` becomes 1024 and
  `retries = 999999` becomes 100, while both defaults are `None`. It contradicted the reasons
  printed directly beneath it, which already name the effective value. The headline now says the
  settings *"could not be used as written, so they have been adjusted"* and asserts nothing about
  what replaced them. **That is this task's own defect surviving for a narrower trigger**, which
  the finding said plainly and which is worth repeating here.
- **`T309-R2` (Medium, blocking) — corrected.** The new fixture interpolated a path into a TOML
  basic string, so an ordinary Windows path made it unparseable and the test measured a parse
  failure. It uses `json.dumps` now, and a Windows-form case is asserted directly.

`SettingsProblem` carries whether the **file** was unreadable, and `summary` composes from it; a file that was read
says *"Some of your settings could not be used… The rest of the file is unchanged"* and names the
way out. `app._joined`'s `problem is None` branch and the value-fallback constructor both mark
themselves readable. The discarded download folder is labelled, because the path printed under
*"downloads will go to the default folder"* was the one being discarded and read as the
destination.

**The maintainer's own file fixed itself while this was being written**: clicking OK and saving
settings rewrote it without the stale `[downloads]` section, which is what *"Saving settings will
overwrite this file"* had meant. The recurrence is therefore no longer reproducible from that
file, and the tests build the original state rather than relying on it.
**Owner:** Implementer
**Priority:** Medium — it fires on every launch, and the first thing it says is false
**Phase:** Phase 4
**Depends on:** nothing
**Relevant context:** `ARC-008` — *"A settings file that exists and cannot be used says so; a
missing one does not"*; `settings.SettingsProblem.summary`; `app._joined`
**Affected surfaces:** `src/tracks_and_trails/core/settings.py`, `src/tracks_and_trails/app.py`
**Risk:** Low
**Required checks:** `pytest tests/unit/test_settings.py tests/ui`; the wording read back against
a settings file that is valid but names a missing folder

#### What it says, and what was true

The maintainer's file is valid TOML and **was read**: `concurrency = 3`, `theme = "light"` and
`default_preset` are all in force. Only `[downloads] directory` names a folder that no longer
exists. The dialog's first line:

> Your settings file could not be read, so default settings are in use.

**Both halves of that are false here.** `SettingsProblem.summary` at `settings.py:1011` hard-codes
it, and `app._joined` reuses `SettingsProblem` for problems that are not read failures at all —
including this one, and an unrunnable ffmpeg. `ARC-008`'s wording is *"exists and cannot be
used"*; a file whose every other value is in use does not match it.

**It also never says what to do.** The remedy is to choose a download folder in Settings, and the
sentence offered instead is *"Saving settings will overwrite this file"*, which reads as a threat
to the file rather than as the way out — and is why it recurs on every launch.

#### Acceptance criteria

- A settings file that **was** read does not claim otherwise. A genuine parse failure still says so
  plainly, and a test covers both rather than the one that prompted this.
- A value that fell back names **which** value and what it fell back to, without asserting anything
  about the rest of the file.
- The message names the action that ends it.
- **`SettingsProblem` stops carrying situations it does not describe**, or is renamed to something
  it does. `_joined` folding an ffmpeg problem into a *"could not be read"* summary is the same
  defect one caller over.

#### Out of scope

- The dialog's stacking, which is `T-308`.
- Writing the settings file unasked to stop the warning recurring. That is a data decision and
  `ARC-008` deliberately does not take it.

### T-306 — The format table is hard to read and hard to choose from

**Status:** In Review — **changes requested at `2181ee1`, corrected the same day; awaiting
re-review.** Ruled by the maintainer on 2026-09-09: legibility only.

#### Correction round 2, 2026-09-09 — third pass, maintainer-authorized

**`T306-R1` (Medium, still blocking at `b76595d`) — corrected.** The conservative AAC fallback was
accepted; the new labels were not. Object type `0x69` is ISO/IEC 13818-3 and `0x6b` is ISO/IEC
11172-3 — MPEG-2 and MPEG-1 Part 3 — and **both cover Layers I, II and III**, so naming them `MP3`
assumed Layer III and labelled an MP2 stream as MP3. They read **`MPEG audio`** now: the family the
identifier establishes, without the layer it does not. Restoring `MP3` fails the literal
expectations.

**That is the same defect twice on one table.** First every `mp4a.*` at AAC, then two object types
at MP3. The mappings were not the problem; reading an identifier as more specific than it is was.

**Minor cleanup, as directed.** The check's sizes are now `MainWindow.DEFAULT_SIZE`, half its
height, and 640x400 — grounded in the application rather than invented — and the checklist
reference is corrected: the format table is rows **5.4**, **5.6** and **5.7**, not section 6, which
is Settings. The unexecutable *"sizes `T-212` row 6 uses"* wording was the implementer's.

**The third pass was authorized by the maintainer on 2026-09-09**, per `TESTING.md` §14, after the
reviewer stopped the loop and asked. The implementer declined to authorize it: §14 puts that with
the maintainer, and an implementer authorizing another pass on their own work is the loop the rule
exists to break.

#### Correction round, 2026-09-09

- **`T306-R1` (Medium, blocking) — corrected.** `mp4a` is a container-level identifier, not a
  codec, and classifying every `mp4a.*` as AAC reported MP3 as AAC. The tables are now split:
  `CODEC_FAMILIES` holds only four-character codes that decide the codec alone, and `mp4a` object
  types are enumerated one at a time in `CODEC_NAMES` — `40.2` AAC, `40.5` HE-AAC, `40.29`
  HE-AAC v2, `69`/`6b` MP3, `a5`/`a6` Dolby. `mp4a.E1`, `mp4a.future` and bare `mp4a` fall through
  to the raw string. The sibling prefixes were audited: `avc1`, `avc3`, `hev1`, `hvc1`, `vp09`,
  `vp08` and `av01` each determine their codec without what follows.
- **`T306-R2` (Low) — corrected.** The new expectations are **literals**, not `codec_name` applied
  to the input, and the tool-tip assertion is exact in both columns rather than accepting `None`.
  Both mutations the review reported surviving now fail, as does classifying `mp4a` by its first
  token.
- **`T306-R3` (Medium, blocking) — check performed; it passes.** The criterion could not be
  executed as written: it named *"the sizes `T-212` row 6 uses"*, section 6 of the checklist is
  Settings, and the checklist specifies no viewport dimensions anywhere. That wording was mine and
  it was wrong. Three sizes are named in the test now, and the check runs inside the **expanded
  staging row** rather than on a standalone table, over both selection modes.

  **It took three attempts and the first two filed or nearly filed a defect that does not exist.**
  Choosing a format *closes* the panel once the selection names a download (`UX_SPEC` §4), so
  asserting reachability after a completing choice measured a panel that had correctly shut; that
  became `T-307` and `T-307` is **Cancelled**. Scrolling to the list's maximum then failed at
  640x400 with the label above the viewport, because content sits below the summary. The check now
  asks whether *a* scroll position shows it whole, in states where the panel is open — and it has
  teeth: pinning the search to the maximum reproduces that failure. Translate the
codec strings, mark what is chosen, demote the ID column; **the fourth option — a recommended row
— is declined**, as it makes the surface advisory and duplicates presets. Still gated on `T-305`
landing first. Raised 2026-09-09 from a real session: *"it's just not very user friendly. There isn't an easy way to see what you are picking,
and most people won't know the number codes."*
**Owner:** Maintainer to rule; Implementer to build
**Priority:** Medium — `REQ-008` makes this the surface where a user picks streams by hand, and
`T-212`'s sitting will meet it
**Phase:** Phase 4
**Depends on:** `T-305` should land first — a table with three honest blanks reads very differently
from one with `Unknown` in every third cell, and the remaining complaint should be measured against
the fixed version rather than the current one
**Relevant context:** `REQ-003`, `REQ-008`; `docs/UX_SPEC.md` §4 and its `P-1`/`P-14` rulings;
`UX-007`
**Affected surfaces:** `ui/format_table.py`, `docs/UX_SPEC.md` §4, and a decision entry
**Risk:** Medium — it reopens a specified surface

#### What bounds this before anything is designed

**`REQ-003` names the columns**, format ID included: *"a sortable table (format ID, extension,
resolution, fps, codecs, bitrate, filesize/estimate, notes)"*. So the number codes cannot simply be
removed — the requirement asks for them, and `REQ-008` is about selecting *by* them. The available
move is to stop them being the first thing the eye lands on, not to delete them.

`P-14` already refuses filtering the table, and `P-1` fixed it as an expanding row rather than a
modal. Neither is reopened here unless the ruling says so.

#### The complaint, separated

1. **Nothing shows what you are picking.** The footer reads `Chosen — none yet`, at the bottom, in
   ordinary weight. Two-stream selection is a two-step act with no running account of it.
2. **The identifiers are machine identifiers.** `614`, `399`, `270` mean nothing without yt-dlp,
   and the codec strings — `vp09.00.40.08`, `av01.0.08M.08`, `avc1.640028` — are worse, because
   they *look* like they should be readable.
3. **The rows are near-identical.** Five rows of `1920x1080 · 24` differing only in codec and
   bitrate, with no indication of which one a person should want.

#### Options, none of them ruled

- **Translate the codec strings** — `avc1…` → `H.264`, `vp09…` → `VP9`, `av01…` → `AV1`, with the
  raw string still available. Cheapest, and it addresses the half of complaint 2 that `REQ-003`
  does not pin.
- **Make the chosen row unmistakable** — the footer states both halves of a merge, and the chosen
  rows are marked in the table itself rather than only summarised beneath it.
- **De-emphasise the ID column** without removing it — narrower, secondary weight, no longer the
  leftmost thing read.
- **Recommend a row.** The largest change: the table would express an opinion, which no part of
  this surface currently does, and it overlaps what presets already exist to do.

**Recommendation: the first three, in that order, and not the fourth without a separate ruling.**
The first three make the table legible; the fourth makes it advisory, which is a different product
decision and duplicates presets.

#### Acceptance criteria

- Whatever is ruled is recorded against `docs/UX_SPEC.md` §4 with the maintainer's authority, since
  §4 is the specification this changes.
- `REQ-003`'s columns all remain reachable, and `REQ-008`'s by-ID selection still works by ID.
- The *"Chosen"* summary is checked inside the **expanded staging row** at named sizes and in every
  selection state the panel stays open for, and the check **records realized dimensions and the
  applied theme** rather than only what it requested — 960x320 requested realizes as 960x424,
  because the layout's minimum wins.
  *(This criterion originally read "at the sizes `T-212` row 6 uses". Section 6 of
  `docs/PHASE_4_CHECKLIST.md` is Settings, the format table is rows 5.4, 5.6 and 5.7, and the
  checklist names no dimensions anywhere, so it could not be executed as written. The wording was
  the implementer's; `T306-R4` required it corrected rather than left standing.)*

### T-303 — A focused check box shifts its own text, and its ring is clipped

**Status:** In Review — built 2026-09-09, awaiting independent review. `QCheckBox` and
`QRadioButton` carry a **transparent** 2px border idle and join `BORDERED_CONTROLS`, so focus
recolours an edge that was already reserved instead of adding one. Contents are stable in both
themes, measured on the style's sub-element rects, and the ring still appears.

**The existing class guard did not close this, which was found by mutation rather than assumed.**
`test_focus_does_not_move_the_control` checks geometry, size hint and viewport — where a control
sits in its layout. Reserving *one* pixel against the two-pixel ring passes all three and still
moves the label, because none of them can see contents reflowing inside an unchanged rectangle.
`test_focus_does_not_move_what_the_control_draws` is the added half and kills that mutant. A
rendered pixel comparison was tried first and rejected: it flagged every bordered control in both
themes, because an image cannot tell a repaint from a reflow.
**Owner:** Implementer
**Priority:** Medium — it is visible on every check box in the application, on the surface Phase 4
added, and `T-212`'s sitting will meet it on several rows
**Phase:** Phase 4
**Depends on:** nothing
**Relevant context:** `T202-R1`; `ui/theme.py`'s `BORDERED_CONTROLS`, `STATE_RULES` and the
`*:focus` rule; `tests/ui/test_colour_is_never_alone.py`
**Affected surfaces:** `src/tracks_and_trails/ui/theme.py`, and a test that closes the class
**Risk:** Low to fix, and the fix must not remove the ring — see below
**Required checks:** `ruff check .` · `ruff format --check .` · `mypy src tests` ·
`pytest tests/ui` · the affected rows re-run by eye in both themes

#### What was observed, and what it measures as

The maintainer reported the *Embed in the file* group looking clipped on its left edge, and the
label text moving when a box is toggled. Measured on the real style sheet, light theme:

| state | text `x` | indicator `x` |
|---|---|---|
| unfocused | 19 | 0 |
| focused | **21** | **1** |

**Checked and unchecked are identical**; only focus moves anything. Clicking a box both focuses
and toggles it, which is why it reads as the toggle doing it.

#### The cause

`*:focus` gives a **2px border** to any control that has none of its own. That is deliberate:
`STATE_RULES` records the ring as the *non-colour* channel for focus, so it survives a greyscale
or monochrome reading. Every other such control compensates the border with padding:

```
QPushButton:focus                    { padding: 3px 9px; }
QComboBox:focus, QLineEdit:focus     { padding: 2px 5px; }
QListView:focus, QTableView:focus, … { padding: 0px; }
```

**`theme.py` contains no `QCheckBox` rule at all.** The ring is therefore added to a widget whose
layout reserved no room for it: content shifts 2px right, and the ring draws at `x=0..1` where the
indicator already sits flush to the group box's content margin, which is the clipped left edge.

**This is the shape `BorderedControl`'s own docstring exists to prevent**, recurring one list over.
That inventory was built because an earlier correction "thickened the border on `QPushButton`,
`QComboBox` and `QLineEdit` — the three controls the finding named — and left every other bordered
control" behind. The **padding-compensation list is a separate, hand-maintained list with no such
guard**, and it has the same gap.

#### Acceptance criteria

- A focused check box draws its ring **without moving its indicator or its text**, and without the
  ring being clipped by the container's margin. Measured, not eyeballed: the `x` of both
  sub-element rects is equal focused and unfocused.
- **The ring still appears.** Deleting it would satisfy the symptom and break the rule it serves;
  `T-304` is where whether it appears *on a mouse click* is decided, and this task must not
  pre-empt that.
- Radio buttons and any other borderless focusable control are checked for the same gap rather
  than assumed clear.
- **A test closes the class, not the instance.** Every control receiving the `*:focus` border has
  a compensating rule, derived from one list rather than two — a padding list that can drift from
  the border list is how this arrived.

#### Out of scope

- Changing when focus rings are drawn at all — that is `T-304`.
- The group box's own margins, unless the measurement shows them to be the cause rather than the
  missing compensation.

### T-305 — The table says *Unknown* where it means *none*, and where it means *nothing to say*

**Status:** In Review — built 2026-09-09, awaiting independent review. Both codec cells and
the notes cell now distinguish *absent* from *unknown*; `describe_codec` takes the stream flag,
and `ABSENT_TEXT` is the word for a stream yt-dlp denied. Mutating either half back kills the new
tests.
**Owner:** Implementer
**Priority:** Medium — it is most of the "lots of unknowns" complaint, and the data to fix it is
already in the model
**Phase:** Phase 4
**Depends on:** nothing
**Relevant context:** `T107-R1`; `FormatInfo.is_video_only` / `is_audio_only` and the two-flag
design at `core/models.py:653–731`; `format_table.describe_codec`; `REQ-003`
**Affected surfaces:** `src/tracks_and_trails/ui/format_table.py`
**Risk:** Low
**Required checks:** `ruff check .` · `ruff format --check .` · `mypy src tests` ·
`pytest tests/ui/test_format_table.py` · the table read by eye against a real probe

#### What is wrong

`UNKNOWN_TEXT` is doing three different jobs, and the model already tells them apart:

| Cell | Rendered | What is true |
|---|---|---|
| **Audio codec**, on a video-only row | `Unknown` | There is **no audio stream**. `entry.is_video_only` is `True` |
| **Notes**, with no note | `Unknown` | There is **nothing to say**, which is not the same as not knowing |
| **Size**, absent | `Unknown` | Genuinely unknown — **this one is correct** |

Every row in the maintainer's screenshot sits under *"Merge a separate video and audio stream"* —
they are video-only by construction — and every one of them reports its audio codec as `Unknown`.

**The model was widened specifically so this could be said correctly.** `T107-R1` is the finding:
the table once rendered *audio only* for a format whose video codec was merely unknown, because a
collapsed field could not distinguish *"there is none"* from *"we do not know"*. `FormatInfo`
carries **two flags** rather than one enum for exactly that reason, and `is_video_only` is written
`is not False` so an unknown stays unknown. `describe_codec(entry.audio_codec)` then flattens it
back to `UNKNOWN_TEXT`, which is the same conflation one layer up.

#### Acceptance criteria

- A video-only row says its audio is **absent**, not unknown; an audio-only row says the same of
  its video. A row where the flag is genuinely `None` still says `Unknown`, and a test covers all
  three cases rather than the easy two.
- A row with no note does not claim the note is unknown.
- **`Size` keeps saying `Unknown`** where it is unknown. The rule the module opens with — a missing
  field never renders as an empty cell — is not being repealed; it is being told which of three
  situations it is in.
- The projection keeps sorting correctly: `SORT_ROLE` is over the underlying value, and a display
  change must not move sorting into the display string (`T-075`).

#### Out of scope

- The table's legibility and selection, which is `T-306`.
- Widening `FormatInfo`. The distinction this needs is already there.

## Ready

### T-304 — Should a focus ring appear when the control was clicked?

**Status:** Ready — **ruled by the maintainer on 2026-09-09: option (2), the keyboard-only
ring.** The options and their costs are kept below as the reasoning the ruling was made on. The
decision entry recording it is part of this task, since the rule it supersedes has a review
finding and a test for authority and no numbered decision.
**Owner:** Maintainer to rule; Implementer to build
**Priority:** Low — it is a comfort question, not a defect. Raised 2026-09-09: *"I don't
necessarily think that mode should be enabled by default — if you are clicking around with a
mouse all of the highlighted boxes are distracting."*
**Phase:** Phase 4 (accessibility and polish)
**Depends on:** `T-303` should land first, so the ring is correct before its trigger is argued
**Relevant context:** `T202-R1`; `STATE_RULES` in `ui/theme.py`;
`tests/ui/test_colour_is_never_alone.py`; `NFR-005`
**Affected surfaces:** `ui/theme.py`, the application's input handling, and the accessibility tests
**Risk:** Medium — it changes a rule that currently has a test and a recorded rationale

#### The question

Qt shows the focus ring wherever focus lands, including a mouse click, because `QCheckBox` and
friends take `StrongFocus`. The web solved this with `:focus-visible`: ring for keyboard, none for
pointer. **Qt has no native equivalent**, so it would be built — track the last input device and
carry it as a dynamic property the style sheet selects on.

#### What makes it a decision rather than a tweak

The ring is not decoration here. `STATE_RULES` records it as the **geometry** channel for focus,
adopted so that focus reads without colour — *"ink against background, which needs no colour to
read"* — and `tests/ui/test_colour_is_never_alone.py` enforces that every state has a non-colour
channel. **No numbered decision governs it**: its authority is review finding `T202-R1` and the
test. So a ruling here would be the first time this is written down as a decision rather than as
code.

#### Options

1. **Leave it.** Every focus is drawn. Costs nothing, and the maintainer finds it distracting.
2. **Keyboard-only ring (`:focus-visible`).** Mouse focus draws no ring; keyboard focus does.
   Standard on the web and in modern toolkits. **It does not weaken the keyboard case**, which is
   what `NFR-005` and the accessibility pass are about. It does mean a control can hold focus with
   nothing showing it, which matters to a mouse user who then reaches for the keyboard — the
   handover is the case to check, not the steady state.
3. **Keep the ring, reduce it** — thinner, or a lower-contrast hue — for every focus. Keeps one
   code path and one rule; likely fails the contrast floor that made it 2px.

**Recommendation: (2), after `T-303`.** It is what the maintainer asked for, it leaves the
keyboard route untouched, and the objection it must answer — focus invisible until the user
reaches for the keyboard — is testable rather than theoretical.

#### Acceptance criteria

- Whatever is ruled is **recorded as a decision with the maintainer's authority**, since the
  current rule's authority is a review finding and this would supersede it in one direction.
- If (2): pressing a key after clicking reveals the ring on the already-focused control, and that
  handover is asserted by a test rather than described.
- `tests/ui/test_colour_is_never_alone.py` still passes, or is amended deliberately with the
  ruling cited — not adjusted to fit.

### T-238 — An xdist UI worker segfaults while entering a thumbnail-store lifetime test

**Status:** **Ready — the guard is Approved at `9e5feae`, and criterion 4 is sharper rather than
met.** The second of its two named steps ran on 2026-08-30, in three arms. **No widget the
application's own routes opened takes the collector's route**; the 95 that survive product shutdown
are `T-273`'s documented baseline and go when its owner step is applied. **The collector-runs-a-Qt-
destructor route is now reproducible on demand** — and doing it aborts the process — but only for
widgets the test helper owns parentless, and on the main thread, so it is **not this task's crash**.
See *Criterion 4, 2026-08-30* and *2026-08-31* below. **The real-session probe has now run on
both pools** — the update route 60 times isolated and once on a real display, the staged-row
thumbnail pipeline once on a real display — and **both were `INCONCLUSIVE`**: the collector never
handled a widget on any of those threads. What criterion 4 still lacks is a product-owned widget
reaching the collector, not another session.

**30 *additional* contended runs, 2026-08-20: zero crashes. The cumulative record is 90 runs, 50 of
them contended.** 40 idle, **12 under 20 busy loops**, **8 beside an `-n auto` integration batch**
— all three rows already in the conditions table below — plus these 30.

*(**The first version of this section said load "had never been tried" and put the total at 70.
Both were wrong, and the entry itself said so** — `T238-R4`. Rows two and three of its own
conditions table are 20 loaded runs, and the paragraph beneath them records that saturation
**refuted** the recommendation to try load. **I acted on the recommendation and not on the
refutation two paragraphs below it**, which is this project's most-documented failure shape: the
sentence most likely to be stale is the one that says what to do next. Nothing was measured wrongly;
the campaign was described as pulling an untried lever when it was adding a fourth condition to
three.)*

**What the design adds over the prior 20, which is the only reason to keep the runs.** The earlier
loaded rows used 20 busy loops (CPU pressure without allocator or GIL contention) and a single
`-n auto` integration batch that **finishes and leaves the target running unopposed**. This ran
**three** `pytest tests/integration -n 4` batches **continuously**, restarting each as it ended, so
every measured run was contended **end to end by real Python allocation and Qt teardown** rather
than by spinning arithmetic. Load achieved on 20 cores: **median 21.4, max 23.9, min 14.2**. Every
run: `3276 passed, 18 skipped`. **It does not reproduce the fault either**, which is the fourth
condition to say so.

**The instrument was proved before the zero was believed.** `T238-R1`'s inverted-order reproduction
was re-run first: swapping the two calls in `tests/ui/conftest.py` still kills the helper subprocess
with **`assert -11 == 0`**, deterministically, on this machine today. **The first attempt at that
control printed a clean 91-passed** — because the reproduction lives in the helper subprocess, not
in an ordinary UI file — which is exactly the blind-probe failure the control exists to catch.
`systemd-coredump` was also confirmed capturing that SIGSEGV, so the dump path was live.
**Independent of the log grep, `coredumpctl` reports no dump of any kind** across the campaign.

*(**The first campaign design was wrong and was discarded after two runs.** It started one competing
batch per iteration and waited for it, so the 39-second target finished and then ran **unopposed**
for the rest of the iteration — a load experiment measuring an idle machine. Recorded because a
negative result from that design would have looked identical to this one.)*

**So repetition is spent at 90 runs across four conditions**, and **criterion 4 is unchanged** —
product-versus-harness is still unestablished. **What it needs is not the guard firing**, and the
first version of this section said it was (`T238-R4`): the 2026-08-16 measurement moved criterion 4
on, and its two named next steps stand — **run the probe against a real session on a display**,
which `tests/integration` cannot answer because a `QCoreApplication` process has no widgets for the
probe's own control, and **establish whether any `QWidget` here participates in a reference cycle**.
A guard firing on a real test would still be evidence; it is not the plan.

**The second of those was attempted on 2026-08-20 and the run refused** (`T238-R5`) — the surfaces
were still retained at the end, so the collector never classified them and its zero says nothing
about cycles either way. **The step is not done and the criterion is not answered**; what the
attempt did produce is `T-273` and a written list of what a run that answered it would have to do.
See *The second step, attempted 2026-08-20* below. *(This paragraph said the two steps "stand", full
stop, for two commits after one of them had been tried — a summary going stale against evidence
lower in the same entry, which is `T238-R4`'s finding recurring in the paragraph `T238-R4`
corrected.)* `T238-R1`, `T238-R2` and `T238-R3` are all **Resolved**. What is delivered is a
harness guard, not a diagnosis: **product-versus-harness is still unestablished**, and this entry
sits under `## Ready` rather than `## Complete` for exactly that reason.

**The review reproduced a segfault, and that is the first one anybody has reproduced here.** Not
the original crash — this investigation has never reproduced that in 60 runs — but its
*mechanism*: swapping the fixture's two calls so the orphan scan runs **before** the drain kills
the helper subprocess with **SIGSEGV (-11), deterministically**. Enumerating live widgets while
deletions are still queued walks a list Qt is about to change. **The order of those two lines is
therefore load-bearing**, which nothing in my own evidence had established, and both the conftest
and `tests/qt_lifecycle.py` now say so where somebody would otherwise tidy them.

**Also verified independently:** all four mutations failed **only** their intended outer
regression, and both guard regressions passed across **20 invocations, 40 tests**.

#### The criterion-6 ruling — maintainer, 2026-08-13 (`T238-R2`, Resolved)

**Criterion 6 is replaced, deliberately and on the record.** It asked that repeated `-n auto` runs
*"materially exceed the pre-fix sample"*, and the pre-fix sample is **60 clean runs**: a larger
clean sample cannot distinguish *the guard worked* from *the crash was always this rare*, which
the reviewer states as plainly as this entry does. **In its place stands `T238-R1`'s evidence** —
each half of the guard fails its own regression under mutation, and neither can be deleted while
the suite stays green.

*(Recorded as a replacement rather than a waiver, which is `T198-R5`'s lesson in a different
costume: a criterion that quietly stops being met is a gate that has been moved without anybody
saying so.)*

#### The criterion-4 ruling — maintainer, 2026-08-13 (`T238-R2`, Resolved)

**`T-238` stays open, and the guard stays in.** Product-versus-harness is not established and
cannot be inferred from a green suite. If the guard ever fires on a real test, that *is* the
evidence criterion 4 asks for and the task closes on it; until then the entry stays open rather
than being closed on the deliverable it happened to produce.

#### What was built — 2026-08-13

**Measurement chose the predicate, and the obvious one was wrong.** *"After every test, assert no
`QAbstractItemView` is awaiting deferred deletion"* is what the entry proposed, and the closest
thing to it that can be observed — *no view created by this test is still alive* — **fails 802 of
839 `tests/ui` tests**. That is not a leak rate: a view parented into a widget tree is **owned**,
and dies with its owner. Two narrower predicates over the same suite return **zero**: a view alive
with *no parent*, and a view alive whose wrapper is otherwise unreferenced. **So what no correct
test produces is an ownerless view**, and that is what `assert_no_orphaned_views` forbids.

**The hazard the stack actually shows is *when*, not *what*.** `_Py_HandlePending` means the
deletion ran at an arbitrary bytecode boundary — inside whatever test was executing, which is why
xdist blamed a file that constructs no view in 2600 lines. So the guard has two halves, and only
one is an assertion:

- **`settle_deferred_deletions(app)`** — `gc.collect()` then
  `sendPostedEvents(None, DeferredDelete)`, at every `tests/ui` test boundary, on the main thread.
  **Measured: 431 of 839 tests had objects awaiting collection or deletion at that point, totalling
  15 457 widgets, 1 001 of them views.** Those destructions were previously running inside later
  tests. **It fixes no *pre-existing* failing assertion** — the suite was green with and without
  it — which is why `T238-R1` was right that it needed evidence of its own, and now has it below.
- **`assert_no_orphaned_views(app)`** — fails the test that leaves a view with no parent, naming
  it. `tests/ui/_leaks_a_view.py` leaks one deliberately and
  `test_a_test_that_leaks_a_view_is_the_test_that_fails` runs it in a subprocess and requires both
  a non-zero exit *and* the orphan message, so a guard reduced to a no-op cannot pass it.

#### `T238-R1` (Medium) — Resolved. The drain had no evidence of its own. It has now.

**The finding is right and it is the one I would have missed.** The leaked-view regression proves
the *assertion* and nothing else: it still fails with `settle_deferred_deletions` reduced to a
no-op, and stashing the whole conftest conflates the two halves. Neither shape the drain exists
for is visible to a parentless-view check — the reviewer's own probe makes the point, a cyclic
parentless view being collected *during* the drain and a parented one dying with its root.

**`tests/ui/_carries_a_deletion.py` is an ordered pair, and the order is the assertion.** The
first test leaves two carry-overs that the orphan check cannot see — a widget tree held only by a
reference cycle, and a `deleteLater()` posted on a **still-parented** view from a fixture
finalizer, after pytest-qt's own drain. The second asserts, **before spinning anything**, that
neither is alive; spinning first would deliver the deletion itself and pass against a conftest
that does nothing.

**Mutated statement by statement, against the regressions rather than against the bad tests:**

| Removed | Which regression fails |
|---|---|
| the whole `settle_deferred_deletions(qapp)` call | `test_a_pending_deletion_does_not_reach_the_next_test` |
| `gc.collect()` alone | the same one |
| `sendPostedEvents(None, DeferredDelete)` alone | the same one |
| `assert_no_orphaned_views(qapp)` alone | `test_a_test_that_leaks_a_view_is_the_test_that_fails` |

**Each half now fails exactly one regression and the other half's stays green**, which is what
makes either one deletable-with-a-test-failing rather than deletable-in-silence. *(The first
version of this measurement ran the deliberately-bad node ids directly and reported the orphan
mutation as "survived" — the bad test **passing** is precisely what its outer regression detects,
so the mutation has to be aimed at the regression, not at the bait.)*

**Cost, measured rather than estimated: `tests/ui` goes from 106.65 s to 121.50 s**, +14.9 s or
**+13.9%**, almost all of it `gc.collect()` per test. Paid deliberately: the alternative is a
native crash attributed to the wrong test, which cost this entry sixty runs and two days.

**Deliberately not extended to `tests/integration`, and that is a decision with a measurement
under it rather than a boundary drawn by hand.** The same predicate was run over that suite:
**0 of 430 tests would trip it**, and the whole suite passes with the drain applied at every
boundary, costing 268.34 s → 281.79 s (**+5%**). So extending it is available and safe whenever
somebody wants it. It is not done here because the crash was in the parallel unit/UI command and
the ruling authorised that guard; widening the blast radius of a change on the same day it is
built is how a small correction becomes a large one.

#### The guard ruling — maintainer, 2026-08-13

**Build it.** The entry conditioned the guard on product-versus-harness being established and then
could not establish it: 60 runs did not reproduce the crash, so repetition is spent at worse than
1-in-60. **The guard is itself the instrument that would establish it** — it fails at the test that
leaks the view, by name, on an ordinary run, instead of waiting for a segfault to land somewhere
else. `docs/project/TESTING.md` §13 already states the principle: the useful signal is the one at the cause.

*(This is a ruling about the *order* of the criteria, not a waiver of any of them. The guard is the
fourth criterion's harness-only branch, taken before the branch condition is proved, because
proving the condition is what it is for.)*

**Status of the original filing** — corrected 2026-08-12 from the retained run log. One of nine observed
`-n auto` unit/UI runs ended when worker `gw7` segfaulted; eight sibling runs passed. **This was
not an assertion failure, and one event in nine runs is a sample, not a measured rate.** Forty
further repeated runs were started to reproduce and characterise it; their result is not yet
recorded here.
**Owner:** Implementer
**Priority:** High — this is a native process crash in the supported parallel test command, not a
timing assertion, and its Qt/PySide lifetime stack belongs to the evidence class that made T-074
and T-128 high-value investigations. One observation does not yet establish product reachability.
**Phase:** Phase 4 — maintenance. **Not a plan deliverable.**
**Depends on:** nothing
**Relevant context:** `T118-R13`, `T-074`, `T-128`, `T-123`,
`tests/ui/test_row_delegate.py::test_deleting_a_closed_store_neither_waits_nor_is_emitted_through`,
`ui/thumbnails.py` (`ThumbnailStore.close`, `_Sink`, the shared `QThreadPool`)
**Affected surfaces:** unknown until the faulting object's lifetime is identified. The active test,
Qt test fixtures/teardown, and `ui/thumbnails.py` are candidates, not conclusions
**Risk:** High to gate integrity and potentially Medium to the product — a worker process is lost;
whether supported application behavior can reach the same native fault is unverified

#### What the retained run actually says

xdist reported:

```
[gw7] node down: Not properly terminated
worker 'gw7' crashed while running
  'tests/ui/test_row_delegate.py::test_deleting_a_closed_store_neither_waits_nor_is_emitted_through'
```

Immediately before that, Python's fault handler reported **`Fatal Python error: Segmentation
fault`**. The current Python frame was inside `occupy_pool()` at `store.pool.start(_Blocker(gate))`,
before the test reached any of its three assertions. The C stack passes through
`QObject::disconnectImpl`, `QAbstractItemView` destruction, and Shiboken's
`BindingManager::runDeletionInMainThread`.

That stack makes Qt/PySide object lifetime and deferred destruction a concrete lead. It does **not**
identify the faulting object, establish that the thumbnail store caused the crash, distinguish an
object left by an earlier test from one created here, or prove identity with T-074/T-128. A native
Qt crash is the shared finding class; a shared cause remains to be demonstrated.

#### The 40 runs, and what the retained stack narrows it to — 2026-08-12

**40 of 40 `-n auto` unit/UI runs passed. Zero crashes, zero failures.** On an otherwise idle
machine, against one observation in nine.

**That is a result, not a null.** The original run happened while the machine was also running
other pytest batches — the same contamination that made `T-228`'s *"one in three"* wrong. **The
one-in-nine figure is not a rate**, and this entry's Status already says so; 40 idle runs now say
it from the other side. Whatever this is, **idle repetition of the supported command does not reach
it**, so the next attempt should reproduce under deliberate host load, as `T-228`'s did.

**The raw stack is retained** at `docs/project/evidence/T238-SEGFAULT-gw7.txt` — `docs/project/evidence/README.md`'s
test is *"could I get it back"*, and 40 runs say no. Trimmed to the crash; the warnings summary is
not evidence.

**What the C stack narrows, read rather than skimmed:**

```
_Py_HandlePending
  → Shiboken::BindingManager::runDeletionInMainThread
    → QAbstractItemView::~QAbstractItemView
      → QObject::disconnectImpl        ← faults here
```

Two things follow, and only two:

- **The faulting object is a `QAbstractItemView`.** `tests/ui/test_row_delegate.py` imports
  `QApplication` and `QStyleOptionViewItem` from `QtWidgets` and **nothing else** — no view class —
  and constructs no view anywhere in its 2600 lines. `ThumbnailStore` is a `QObject`, not a view.
  **So the destroyed object was not created by the test xdist named**, which is exactly the
  attribution trap this entry warned about: *"while running"* names the active node.
- **It ran at `_Py_HandlePending`** — a deferred deletion executing at an arbitrary bytecode
  boundary, here inside `occupy_pool`'s `store.pool.start(...)`. That is why the Python frame points
  at this test while the destructor belongs to something else.

**What it does not establish**, and must not be written as though it did: which object, which test
created it, whether `thumbnails.py` is implicated at all, or identity with `T-074`/`T-128`. A
`QAbstractItemView` destructor under Shiboken deferred deletion is the same *class* of stack as
`T-128`'s — a QObject destroyed at a moment nobody chose — and `T-128` was a **harness** defect. That
is a lead, not a conclusion, and the third criterion below forbids treating resemblance as cause.

**The search is therefore narrower than the entry assumed**: not "what is wrong with this test", but
**which earlier test in the same worker leaves a view whose deletion is still pending**. The
`qt_lifecycle` orphan-timer guard (`T-128`, `tests/integration/conftest.py`) is the existing shape
of an answer — a per-test check that fails at the cause rather than at the crash — and `tests/ui`
has no equivalent for *views*.

#### Reproduction is not a viable strategy at this rate — 60 runs, 2026-08-12

| Conditions | Runs | Crashes |
|---|---:|---:|
| `-n auto` unit/UI, idle machine | 40 | **0** |
| `-n auto` unit/UI, host saturated (20 busy loops on 20 cores) | 12 | **0** |
| `-n auto` unit/UI **while an `-n auto` integration batch runs beside it** | 8 | **0** |

**Sixty runs, no reproduction — including the third row, which is the closest reconstruction of the
original conditions available.** The observation happened while other pytest batches were running,
so that shape was tried deliberately rather than as an afterthought.

**The second row also refutes a recommendation this entry made two paragraphs earlier.** Having
watched saturation reproduce `T-228` at 3-in-5, I wrote that the next attempt should reproduce under
deliberate host load. It does not. Different defect, different lever — the same mistake as comparing
this to `T-228` in the first place, made a second time in a smaller way.

**So repetition is the wrong instrument here.** At worse than 1-in-60 the cost of catching it again
is unbounded, and the retained stack already says more than another crash would: the object is a
view, and the test it was blamed on never makes one.

**What is worth building instead, proposed rather than done:** a `tests/ui` guard in the shape of
`qt_lifecycle.fail_on_orphaned_timers()` — *after every test, assert no `QAbstractItemView` is
awaiting deferred deletion* — which fails **at the test that leaked the view**, by name, on the
first ordinary run, instead of waiting for a segfault to land somewhere else. That would satisfy the
fourth criterion's *"a guard that fails before a worker dies"*, and `docs/project/TESTING.md` §13 already
states the principle: the useful signal is the one at the cause.

**Not built here**, because the fourth criterion is conditioned on product-versus-harness being
established and it is not. This is the Implementer proposing the next step, not taking it.

#### Scope

Reproduce and diagnose the **worker SIGSEGV** under the supported parallel unit/UI command. Capture
the test order and teardown state around the crash, because xdist's *"while running"* attribution
names the active node, not necessarily the object whose deferred deletion faulted.

Do not fold it into T-228: that task concerns `multiprocessing.Queue` delivery in spawned
integration workers. No assertion timed out here, so changing the interaction budget or pool-drain
deadline is not a candidate correction. Preserve the three existing contracts: deletion does not
block the GUI thread, the pool can drain, and late work does not emit through a deleted `QObject`.

#### Acceptance criteria

- Reproduction evidence records the process signal/exit, Python and native stacks, explicit xdist
  worker count, and the tests immediately preceding the active node; raw failing logs are retained
- Serial, isolated, module-order, and explicit xdist-count runs distinguish a defect in this test
  from deferred destruction or contamination left by another test
- The faulting object and lifetime edge are identified before claiming identity with T-074 or
  T-128; stack resemblance alone is not a cause
- **Re-scoped 2026-09-04** — see `T-289`'s *Ruled 2026-09-04*, which governs both. Product versus
  test-harness is established **by enumerating where the precondition is written**, not by catching
  the fault: 91 parentless product-widget constructions in the harness against 4 in the product, and
  77 against 2 for the item-view-capable subset. The guard stays in, and a firing is still the
  evidence that would reopen this. *(The original wording follows; it is superseded, not deleted.)*
- Product behavior versus test-harness behavior is established. A product-reachable fault gets a
  deterministic regression; a harness-only fault gets a guard that fails before a worker dies
- The original responsiveness, pool-drain, and no-emission-through-deleted-object assertions stay
  intact; no timeout is raised to make the crash disappear
- Repeated `pytest -n auto tests/unit tests/ui` runs after the correction materially exceed the
  pre-fix sample without another worker loss

#### Where each criterion stands — 2026-08-13

| # | Criterion | State |
|---|---|---|
| 1 | Reproduction evidence, raw logs retained | **Met for the one observation** — `docs/project/evidence/T238-SEGFAULT-gw7.txt`. **Not reproduced since**, in 60 runs |
| 2 | Serial/isolated/module-order runs distinguish this test from contamination | **Met, and it is what redirected the search.** The named test's file constructs no view; the faulting object came from elsewhere in the worker |
| 3 | The faulting object and lifetime edge identified before claiming identity with `T-074`/`T-128` | **Half met.** The *class* is identified — a `QAbstractItemView` destroyed under Shiboken's cross-thread deletion queue — and the specific object is **not**. No identity with either task is claimed |
| 4 | Product versus harness established; harness-only gets a guard that fails before a worker dies | **Still open — and no longer open with nothing behind it.** The mechanism is identified and is **product-reachable in principle**; see the 2026-08-16 measurement below. The guard remains delivered, and if it ever fires on a real test that is still evidence |
| 5 | The three original assertions stay intact; no timeout raised | **Met** — `test_deleting_a_closed_store_neither_waits_nor_is_emitted_through` is untouched, and `INTERACTION_BUDGET_SECONDS` is unchanged |
| 6 | ~~Repeated `-n auto` runs materially exceed the pre-fix sample~~ → **each half of the guard is mutation-checked independently** | **Replaced by maintainer ruling, 2026-08-13; met as replaced and verified at review.** Four mutations, four failures, each in **only** its intended outer regression — see `T238-R1` |

#### Criterion 4, 2026-08-16: the mechanism, measured and then found to be the wrong question

**The approach.** Criterion 4 has stayed open because it *cannot be inferred from a green suite*.
So this measures the fault's **one precondition** instead of waiting for the fault: the retained
stack shows `~QAbstractItemView` under `Shiboken::BindingManager::runDeletionInMainThread`, and
Shiboken only queues a deletion for the main thread when the wrapper's last Python reference was
dropped **somewhere else**. A `weakref.finalize` callback runs on whichever thread performed that
decref, so the precondition is directly observable. `tools/t238_widget_thread_probe.py`.

**The measurement, over a full serial `tests/ui` run:**

| | |
|---|---|
| `QWidget` classes instrumented | 92 |
| widgets constructed | 14 697 |
| finalisations observed | 8 853 |
| **finalised off the main thread** | **0** |

**The instrument's own positive control passed first, and it had to.** Two earlier versions
reported *zero off-thread finalisations over the whole suite* while measuring nothing at all —
first because Shiboken gives every class its own `__init__` slot, so patching `QWidget` caught no
real widget; then because patching a subclass that *inherits* `__init__` nests a wrapper per
hierarchy level. **Neither was visible in the output**, and "no widget was finalised off the main
thread" is exactly what a blind probe prints. The probe now drops a widget on a named worker
thread and refuses to report unless it sees it. `docs/project/TESTING.md` carries this as a rule.

**Then a survey of what the product's threads hold, which is where it got interesting.** Every
thread mechanism the product has was read: `ResultPump` (a `QThread` holding a queue, a job id, an
`Event` and a dict of `Signal`s), `ytdlp_service._Task` on the shared pool (a `_Sink` `QObject` and
a bound method of a `QObject`), `thumbnails._ReadFromDisk` / `_DecodeAndStore` / `_SweepTask` (a
`_Sink`, `str`, `Path`, `bytes`, `set[str]`), and the persistence writer's `QThread` (a `_Worker`
`QObject` and a callable). **Not one holds a `QWidget`.**

**And that is not sufficient, which is the finding.** Python's cyclic collector runs on whichever
thread crosses the allocation threshold, so **a widget reachable only from a reference cycle is
decref'd wherever `gc` happens to run — with no thread ever holding a reference to it.**
Demonstrated, in twelve lines, by `demonstrate_the_gc_route()` in the probe:

```
$ QT_QPA_PLATFORM=offscreen .venv/bin/python tools/t238_widget_thread_probe.py
the widget's last reference was dropped on: t238-gc-demo-worker
```

**So "who holds a reference" is the wrong question for this criterion. The question is who runs
`gc`** — timing rather than ownership. Both of the product's pools allocate (`QImage` decodes,
most obviously), so **the precondition is product-reachable in principle**, and the harness-only
reading cannot be assumed.

**What this establishes and what it does not.** It identifies the mechanism and shows it is
available to the product; it does **not** show the product reaches it in a real session, and it
does not reproduce the crash. It also explains the shape of the evidence better than anything
before it: a fault needing `gc` to fire on a pool thread at the moment a widget-bearing cycle is
garbage is one that appears once on a loaded machine and never again in 60 clean runs.

**What criterion 4 needed next as of 2026-08-16**, and it was no longer "wait for the guard to
fire". **Both items have since been answered in part; see *Criterion 4, 2026-08-31* for what is
owed now** (`T289-R15`, third pass — this read as a live request for a session that has since been
driven, which is the same defect dated one section further down):

- **Run the probe against a real session, not the suite** — `tests/integration` cannot answer it
  (a `QCoreApplication` process has no widgets at all, so the probe's own control would fail), so
  this needs the application driven on a display with the thumbnail pool actually working.
  **Run on 2026-08-31, on both pools and on a real display, and inconclusive both times**
- **Establish whether any `QWidget` in this application participates in a reference cycle.** If
  none does, the `gc` route is closed and the harness reading is back; if one does, criterion 4's
  *product-reachable* branch is the live one and it wants a deterministic regression, not a guard.
  **The 2026-08-30 arms bear on this without answering it as put**: no widget the application's own
  routes opened was parked while its Qt widget was still alive, which is the consequence this
  bullet cares about — *participates in a cycle* is a stronger predicate than `DEBUG_SAVEALL`
  parking establishes, as that section says of itself

#### The second step, attempted 2026-08-20: the run refused, and criterion 4 is unanswered

**`tools/t238_widget_cycle_probe.py`, offscreen on `kirk`.** It composes the application, opens the
three surfaces the window's own routes open — `open_add_dialog()`, `open_settings()`,
`show_about()` — tears it down through `composition.shutdown.begin()`, and then reads which
`QWidget`s **the cyclic collector freed**, with `gc.DEBUG_SAVEALL` armed so the collector's own
verdict is legible.

**The predicate is "freed by the collector", not "in a cycle", and the difference is the whole
measurement.** A widget held *by* a cycle is not itself in one — its own component has size one —
and it is still freed by `gc` rather than by refcount, and still decref'd on whatever thread
collected. Cycle *membership* would have answered a neighbouring question and missed exactly the
shape `demonstrate_the_gc_route()` demonstrates.

| Measured | Result |
|---|---|
| `QWidget`s live with every route open | **159** |
| `QWidget`s live after the application's own shutdown | **159** |
| `QWidget`s freed by the cyclic collector | **0** |
| **Other** objects freed by the collector in the same window | **30** |
| Exit code | **3 — refused** |

*(**That last row read "0 objects" for one commit and was wrong.** It was quoted from a scratch
diagnostic that was holding the objects it was counting — `gc.get_referrers` returned the very
lists I had put them in — rather than from the probe. The probe reports it now, which is the only
place it can be read from honestly. The correction **strengthens** the result rather than softening
it: the collector was **not** idle during the measurement, so *no widget was collected* is a fact
about widgets and not about the collector having nothing to do.)*

**The probe refused, and the first version of this section then answered anyway** (`T238-R5`). It
said the `gc` route was closed through these surfaces, that the trees were *"not garbage"*, and that
criterion 4's harness branch was selected. **All three are withdrawn.** The run exits **3** and says
its own zero is not a result about cycles; a section that quotes the refusal and then draws the
conclusion the refusal forbids is the same document giving two answers, which is the shape this
project keeps finding.

**Four reasons the counts do not reach that conclusion**, and each is a thing a future run would
have to fix rather than a caveat to note:

1. **Retention is not the absence of cycles.** A still-reachable graph is not classified by the
   collector at all, so it may contain any number of them. *"Not garbage"* described what the
   collector was prevented from deciding.
2. **Equal aggregates do not establish identity.** 159 before and 159 after does not say they are
   the same 159 widgets, and `0 widgets among the parked garbage` is a count, not a statement about
   which widgets those were.
3. **The forced `gc.collect()` after the result is not recorded.** It runs in the helper's `finally`,
   after the result is read and after `DEBUG_SAVEALL` is lowered, so whatever it frees is invisible.
4. **Five product-reachable screens are not covered.** The format table, template editor, playlist
   picker, options dialog and preset manager are reached from a staged row. Criterion 4 asks about
   **any** application widget.

**Criterion 4 stays open**, and what would close it is now specific: a measurement that **releases
or otherwise controls the retention root**, **tracks the identities** of the widgets it decides
about, **observes the collector after that release**, and **covers the whole application-widget
scope**.

**The refusal is the instrument working, and it is why an earlier number was thrown away.** The
very first run printed `0 freed` and nothing else, and that reads exactly like a clean result; *nothing was freed by the collector* and *nothing was freed at all* produce the same zero
and are opposite answers. The before/after widget counts are now part of the instrument, and it
**exits 3 rather than reporting** when the surfaces are still standing. Its **self-test runs in both
directions first** — it must *see* a widget reachable only from a cycle and must *not* name one
freed by refcount — because the sibling probe shipped two defects that made it report confidently
about nothing, **one of them a clean-looking zero** across the whole UI suite. *(That probe's
docstring calls both defects "clean"; only the first was. The second over-counted a widget five
times and was caught by a run taking three times as long, not by reading its output — a distinction
worth keeping, since it is the difference between an instrument that lies quietly and one that lies
loudly.)*

**What this does not establish.** *Why* the tree is retained is not identified here: the window's
Python referrers are its own bound methods and closure cells, and an attempt to attribute those to
C++ signal connections was **contaminated by the diagnostic's own lists** and is withdrawn rather
than reported. **The five uncovered screens were also called a deliberate scope and are not one**
(`T238-R5`): avoiding a second inventory of screens is a real constraint (`T200-R3`), but it does
not make those screens unreachable, and calling an omission a choice is how a bound stops being
read as a bound.

**`T-238` stays `Ready`.** This narrows the question and does not close it, and the entry is not
moving to `Complete` on a measurement that argues the opposite of the deliverable it already has.

#### Criterion 4, 2026-08-30: the collector's route is reproduced, and it is not this crash

`docs/project/evidence/2026-08-30-T238-criterion-4-widget-collection.md`. Three arms, each deterministic.
Census in all three: **364** widgets — 159 opened by the application's own routes, 205 constructed
by `tests/ui/surfaces.py`, the same inventory `tests/ui/conftest.py` audits (imported rather than
restated, because two lists of them would drift).

| Arm | Constructed screens | Window | Parked | **Live when parked** | Survivors | Outcome |
|---|---|---|---:|---:|---:|---|
| **A** | closed + `deleteLater` | product shutdown alone | 17 | **0** | 95 | no live destruction |
| **B** | **dropped for the collector** | product shutdown alone | 24 | **24** | 122 | **release → SIGSEGV** |
| **C** | closed + `deleteLater` | **+ `T-273`'s owner step** | 67 | **0** | **0** | no live destruction |

**The first version of this section was wrong and is withdrawn** (`T238-R7`). It reported arm A's
17 as *"widgets freed by the cyclic collector"* and called them the crash's precondition. **All
seventeen were already-dead wrappers**: the probe had `deleteLater`'d and flushed `DeferredDelete`
first, so Qt destroyed the C++ widgets and the collector parked the Python halves. Clearing a dead
wrapper runs no destructor and reaches no deletion path. The reviewer's replay — `shiboken6.isValid`
read while `gc.garbage` was still populated — is what separated the number from the claim, and the
probe now reads validity there itself. *"They are in cycles"* was also stronger than the predicate:
`DEBUG_SAVEALL` parks what a collection frees, and an object can be there because its only referents
were cyclic.

**No widget the application's own routes opened was parked while its Qt widget was still alive.**
That is the invariant across all three arms — **not** the same arithmetic in each, which is what
this said and was wrong (`T238-R9`). The arms do not release the same widgets:

| Route-opened widgets, 159 | parked | by refcount | still alive |
|---|---:|---:|---:|
| Arms A and B — window left to product shutdown | 0 | 64 | 95 |
| Arm C — `T-273`'s owner step applied | **50** | **109** | 0 |

Arm C parks 50 of them, and **all 50 are already-destroyed wrappers**: the owner's `deleteLater`
ran their destructors before the collector saw them. The claim survives the correction; the number
64 belongs to two arms of the three. The probe now prints the split per origin, because a record
quoting one arm's arithmetic for all three is quoting a number no run produced.

**Arm B reproduces the mechanism on demand, and demonstrating it aborts the process.** With Python
owning the C++ objects and only the collector freeing them, 24 wrappers park **with their widgets
still alive**, and the release dies: `gc_collect_main` → `_Py_Dealloc` → shiboken → `~QDialog` →
`hide_helper()` → the offscreen plugin → `QCursor::pos` → **SIGSEGV, 3 of 3 runs**. The upper half
is `T-238`'s retained stack and `T-289`'s dump — **the cyclic collector running a Qt widget
destructor**. **It is `T-289`'s stack exactly** — that dump's pool thread runs
`_Py_HandlePending` → `gc_collect_main` → `_Py_Dealloc` → shiboken → `QWidget::~QWidget`, the same
frames in the same order. **Its relation to `T-238`'s own crash is analogous rather than
identical** (`T238-R10`): the retained stack here is `~QAbstractItemView` under
`runDeletionInMainThread`, Shiboken's **queued cross-thread** path, which arm B never enters. Both
are the collector running a Qt destructor; only one of them is this task's. **Arm B is not this
task's crash** — main thread, offscreen plugin, helper-owned widgets — and it is the first time the
route has been made to happen on demand.

**Those widgets are the helper's, and that bound is the whole reason arm B is not the answer.**
`tests/ui/surfaces.py` builds the five **parentless**, so Python owns C++ objects the product would
have parented. In the product they have a parent, and dropping a wrapper then destroys nothing.

**The 95 survivors are `T-273`'s documented baseline** (`T238-R8`), and the previous section's
*"a tree that task was meant to have released"* is withdrawn with its incomplete-or-second-instance
speculation. `T-273` ruled that `shutdown.begin()` does **not** own the window's lifetime — the
`composed` fixture does, with `window.deleteLater()` and a **receiver-scoped** `DeferredDelete`
flush. **Arm C applies that step and every censused widget goes: 0 survivors.** Arms A and B omit
it, which is why the tree stands there.

**Two method corrections, either of which changes the answer.** `processEvents()` does not run a
`deleteLater()` — Qt delivers `DeferredDelete` only from an event loop. And automatic collection is
**off** for the measured phase: a widget freed by a generational collection during teardown would
be gone before `DEBUG_SAVEALL` was armed and would be filed under *freed by refcount*, which is the
exact event being measured. The run is therefore not natural teardown timing, deliberately.

**The instrument refuses rather than reporting when it cannot see.** Three controls run first: a
widget reachable only from a cycle is parked by its own tag **and valid at that moment**; a
refcount-freed widget is not named; and a parentless `QListView` outliving the self-test makes the
probe refuse — because the first version censused its own positive control and reported it as a
product finding. **Three instruments in this family have now reported confidently about nothing.**

**What criterion 4 needed as of this section, and how much of it has since been run**: the
real-session probe — the application on a display with the thumbnail pool working — and a widget the
*product* owns from Python reaching the collector. Arm B shows what happens when one does; nothing
in these three arms shows the product holding one. **The probe half ran on 2026-08-31 — both pools,
on a real display — and the widget half did not happen there either.** This paragraph asked for a
session that has since been driven, and said so two lines above the section recording it
(`T289-R15`, second pass); it is kept as the statement of what was owed *then*, and the section
below is what is owed now.

#### Criterion 4, 2026-09-03: counted rather than sampled — **and the first count was wrong**

**Corrected 2026-09-03 after `T238-R11`.** The first version of this section reported *"89
parentless, 30 item-view sites, none in the product"* and drew an asymmetry from it. **Two of those
three numbers were wrong and the third was a category error**, so the numbers are restated below and
the conclusion is not.

**Why count at all.** Six probes asked *"is a product widget reaching the collector right now?"* — 60
isolated sessions, two real-display runs, a forced collection at two sampled moments, the thumbnail
pipeline on its own pool threads — and every one answered no. That question has the regress
`T-289`'s audit named: another null sample cannot separate *there is none* from *we sampled the
wrong instant*. A widget can only be Python-owned if it is left without a Qt parent, so the sites
where this is even possible are finite and countable.

**Three predicates, and merging them is what went wrong.** *Parentless at construction*, *still
Python-owned afterwards*, and *able to destroy an item-view descendant* are different questions.
`tools/t289_ownership_audit.py` now reports the first and third separately and does not claim the
second at all.

| | constructions | parentless at the call site | of those, classes that **can** own an item view |
|---|---:|---:|---:|
| `src/tracks_and_trails` | 162 | 4 | **2** — `MainWindow`, `QueueView` |
| `tests/` | 92 | **91** | **77** |

**What was wrong, itemised, because the corrections are the useful part:**

- **`parent=None` was counted as a parent.** `is_parented` returned true for any `parent=` keyword
  without looking at its value, so four real sites were hidden. 89 → **91**. Fixed for the keyword
  and the signature-mapped positional form, with a self-test arm for each, both verified by mutation.
- **The item-view set was chosen by eye and was incomplete — twice.** It named four classes;
  `PresetManager` and `OptionsDialog` each own a `QListWidget` directly, and ownership is
  **transitive** — a `MainWindow` reaches a `QListView` through its queue. Rebuilt structurally, it
  was **still** wrong: seeding only from *constructions* missed a product class that **is** an item
  view. `EntryTable(QTableView)` constructs nothing and owns nothing, and six `PlaylistPicker` sites
  reach an item view through it. 71 → **77** (`T238-R11`, second round). The seeding now includes
  classes transitively derived from an item view, and the self-test pins both routes.
- **"None in the product" was false.** `src` has **2** parentless sites whose class can own an item
  view, and `build_queue_view()` is reached — `main_window.py` adopts it with `setCentralWidget`
  two statements later. That adoption is exactly the *second* predicate, which this tool does not
  measure, and stating "none" merged it with the first.

**`can own` is not `does own here`, and the tool now says so in its own output.** `MainWindow` builds
its queue only when equipped, so 71 is an **upper bound** on harness sites that could run
`~QAbstractItemView` — not a count of the ones that would. Deciding a given site needs the
construction's arguments, which an AST reading does not have.

*(The count has been corrected twice under review — 89 → 91 for `parent=None`, 71 → 77 for a class
that is an item view rather than owning one. Both errors ran in the direction of the conclusion this
section was drawing, which is the reason it is written up as an argument that has been wrong rather
than as a finding.)*

**What this establishes.** A real asymmetry in where the *precondition* is written — 91 parentless
product-widget constructions in the harness against 4 in the product, and **77** against 2 for the
item-view-capable subset. Nothing more. It does **not** identify the faulting object (criterion 3),
it does not establish what remains Python-owned after construction in either tree, and it is a
static reading blind to widgets Qt itself constructs.

**It does not move criterion 4 and is not offered as doing so.** The maintainer's 2026-08-13 ruling
sets the bar at the guard firing on a real test. This is an argument, it has now been wrong once,
and the corrected version is recorded so the next reader inherits the numbers rather than the claim.

#### Criterion 4, 2026-08-31: both halves of the real-session step have run, and neither answers it

**The update-route half** is `T-289`'s driven measurement — 60 isolated sessions at `179f73e`,
recorded in that entry under *The driven measurement* — plus the reviewer's own run of the same
route on a **real display** at `948f837`. Both answer in the direction the three arms above did:
**no widget the product owns reached the collector**, on the very pool thread the crash dump names.

**The thumbnail half ran too, and it is the one this criterion asked for.** In the review of
2026-08-31 a driver composed the real application with the spawned-fixture worker, staged the
recorded Archive.org row through the add dialog's own debounce, and let the delegate start the real
`ThumbnailStore` pipeline; the public JPEG was fetched into a disposable cache and published as a
pixmap. `_ReadFromDisk`, `_DecodeAndStore` and `_SweepTask` each ran on their own pool thread.
**647 widgets watched, 12 collections — every one of them on the GUI thread, none on any thumbnail
task thread**, 0 destructions off the GUI thread, 0 near misses. `INCONCLUSIVE`.

*(**Superseded by the re-scope of 2026-09-04** — see `T-289`'s *Ruled 2026-09-04*, which governs
both criteria. What follows was true when written.)*

**Criterion 4 stays open, and the reason has moved.** It is no longer *"nobody has run it on a real
session with the pool working"* — that has now been run. What is missing is the thing the criterion
is actually about: **a widget the product owns from Python reaching the collector**. The pool did
its work and the collector never fired on those threads at all, so there was again nothing for it to
get wrong. **Forcing a collection there was deliberately not done**: on a live desktop that converts
the measurement into the hazard it is measuring, which is a choice for the maintainer and not a
thing to slip into a probe.

---

---

---

## Proposed — Phase 0

## Proposed — Phase 1

## Proposed — Phase 2

### T-121 — The phase-exit clip server aborts connections on hosted Windows

**Status:** **Proposed — narrowed 2026-08-03, and still open.** Two of its three parts are struck
off: the misleading assertion and the missing `ConnectionAbortedError`. What remains is the part
nothing here can reproduce — **why the loopback connection aborts under load on hosted Windows.**
Filed rather than fixed inline (`AGENTS.md` §7): it is not `T-118`'s.

**It is now latent for two independent reasons, and only one of them is about the defect.** It did
not recur in run `30859578131` — which is not the same as resolved (`COORD-R21`) — **and the
configuration it appeared in is no longer exercised at all.** It only ever failed on hosted
`windows-latest`, and that job does not run while `WINDOWS_RUNNER` points at `STARBASE`
(`docs/project/TESTING.md` §10). *Not running the job that found a defect is not evidence about the defect*,
and in six weeks the silence will read as resolution unless this paragraph is here.

The current red on `main` belongs to nothing: `T-122`'s ratio oracle is corrected.
*(This read "it is the only thing red on `main`" until 2026-08-03, which stopped being true the
moment `T-118`'s own scaling gate failed and this test passed.)*
**Owner:** Implementer
**Priority:** Medium — a gate that fails for its own fixture's reasons is a gate that will be
dismissed, which is `T118-R10`'s lesson in a different costume
**Phase:** Phase 2 (its gate), though the defect is in test infrastructure
**Relevant context:** `tests/integration/test_phase_2_exit.py`, its `media_url` fixture,
`tests/network/conftest.py`
**Affected surfaces:** `tests/**`
**Risk:** Low to fix, and it is *not* a production defect

**`test_every_queued_job_eventually_starts_as_slots_free` failed on hosted `windows-latest` while
passing on `STARBASE`.** The assertion reads:

```
0 of 5 jobs were still QUEUED after Add with nothing else done
Final: {'af90cb': 'completed', '660db5': 'completed', '83cc82': 'failed',
        'bdd939': 'completed', '7cbf8e': 'completed'}
```

**Read the numbers before the message.** Zero jobs were still `QUEUED`, so the behaviour the test
exists to prove — that a queue drains with no user action after Add — *held*. Four of five
completed. The fifth **failed**, and the captured stderr says why:

```
ConnectionAbortedError: [WinError 10053] An established connection was aborted
by the software in your host machine
```

That is the test's own `ThreadingHTTPServer` losing a connection to its own client, twice, on the
loopback interface. The predicate demands all five `COMPLETED`, so one aborted download reddens a
test whose subject is admission.

**The message is now misleading, which is the part worth fixing.** It reports the `QUEUED` count
and concludes "nothing admits durable queued intent" — a sentence that is false whenever the count
it prints is zero. A reader who trusts the prose over the dict diagnoses the scheduler.

#### Scope

- Make the fixture server survive an aborted client connection rather than propagating it.
- Distinguish the two failures in the message: *jobs did not start* is the defect this gate exists
  for; *a job started and its download failed* is a different sentence and should say so.
- Neither reproduces on Linux, and it is hosted-Windows-only so far — `STARBASE` ran the same test
  in the same run and passed. Codex separately reported 16 localhost-server tests denied outright
  by its sandbox, so this fixture is fragile in more than one constrained environment.

#### Out of scope

- The download path itself. Nothing here suggests a production defect: the worker did what a
  worker does when a server drops the connection.

#### Corrected 2026-08-03 — the two parts that could be fixed without reproducing it

**The assertion named the wrong defect.** It printed the `QUEUED` count and then concluded
"nothing admits durable queued intent" *whatever that count was*, so a run where every job started
and one download failed reported "0 of 5 still QUEUED" and blamed admission — the one part that was
working. It now branches: a stalled queue says so, and a queue that drained with a failed download
says **that**, and points at the clip server.

**`ConnectionAbortedError` was missing from the handler.** `media_handler` already caught
`BrokenPipeError` and `ConnectionResetError` with the comment *"the expected end of a killed
download: the worker went away mid-stream"* — and `ConnectionAbortedError` is that same condition
on Windows. Its absence is why the abort escaped to `socketserver`, which printed a traceback for a
state two lines of the fixture already called expected. Added in **both** copies: the shared
`media_handler` in `test_end_to_end.py` that `test_phase_2_exit.py` imports, and `test_manager.py`'s
own.

**Neither makes the download succeed**, and neither is claimed to. Swallowing the abort stops the
noise; the connection still died mid-stream and that is what failed the job. Both changes are
improvements a reader can verify without Windows, which is exactly why they were worth doing
separately from the part that needs it.

---

### T-106 — Decide the Linux packaging format before Phase 5

**Status:** Proposed — **filed 2026-08-01**, from the Phase 5 roadmap review. `IMPLEMENTATION_PLAN.md`
requires this decision *before the first build* and it does not exist.
**Owner:** Architect / maintainer decision
**Priority:** Medium — nothing is blocked until Phase 5, and the answer shapes work well before then
**Phase:** Phase 5 prerequisite
**Depends on:** nothing
**Relevant context:** `REL-001` (ship frozen artifacts, no Python on the user's machine),
`IMPLEMENTATION_PLAN.md` §Phase 5, `LIC-001`, `NFR-009` (Qt stays dynamically linked), `OPS-001`
**Affected surfaces:** `docs/project/DECISIONS.md`, and later `packaging/`
**Risk:** Medium — taken late, it constrains a build that has already been written

#### Scope

§Phase 5's trigger reads: *"A `REL-` decision recording the Linux packaging format must be accepted
before the first build."* The only `REL-` entry is `REL-001`, which decides that artifacts are
frozen and self-contained and says nothing about **format**. The deliverable list says only
"Linux: packaging per the `REL-` decision" — pointing at an entry that does not exist.

**Why it is worth taking early rather than at Phase 5.** The candidates differ in ways that reach
back into the build: AppImage wants everything in one tree and is closest to what PyInstaller
already produces; Flatpak has its own runtime and sandbox, which changes how the application finds
`ffmpeg` and where it may write (`NFR-004`, `REQ-024`); a `.deb`/`.rpm` pair means system packaging
per distribution and a dependency story rather than a bundle. `NFR-009` constrains all of them —
Qt must stay dynamically linked (`LIC-001`'s LGPL condition).

#### Acceptance criteria

- A `REL-` entry naming the format, with the rejected alternatives and **why**, in the house style
- States how the choice interacts with `REQ-024`'s ffmpeg detection and `NFR-004`'s directories,
  since that is where a sandboxed format differs most from a bundle
- States what it means for `NFR-009`, and how that is checked in the release gate
- Names its reopening condition

#### Out of scope

- Building anything. This is the decision; Phase 5 owns the packaging work
- Windows, which `OPS-001` already settles

---

### T-104 — Hand a second launch's URL to the running instance

**Status:** Proposed — **filed 2026-08-01 by `T-087`**, which built the ownership half of `ARC-006`
and deliberately not the attach half.
**Owner:** Implementer
**Priority:** Low — `T-087` satisfies exit criterion 4 and `A-004` by refusing; this is the nicer
half of "attaches **or** refuses"
**Phase:** Phase 2
**Depends on:** `T-087`
**Relevant context:** **`ARC-006`** and its 2026-07-29 amendment, `A-004`, `REQ-001`
**Affected surfaces:** `app.py`, a new channel module
**Risk:** Low — the ownership guard already prevents the harm; this only improves the outcome

#### Scope

`ARC-006` keeps `QLocalServer`/`QLocalSocket` as an **attach channel**, and is explicit that this is
what makes *attach* possible rather than only *refuse*: "a second launch can hand its URL to the
running instance and raise its window. A lock file can only say no."

`T-087` built the ownership lock and stopped there, because the criterion it owns is satisfied by
refusing. Today a user who double-clicks the application a second time — or opens a link with it
while it is running — gets a message box naming the running instance and nothing happens to the URL.

**The channel is started by whoever wins the lock, and never decides who owns the database.** That
separation is the whole point of the amendment and must survive this task: the loser connects to the
channel and hands over; it does not attempt to become a server.

#### Acceptance criteria

- A second launch with a URL passes it to the running instance, which enqueues it, and the second
  process exits reporting that it did so
- The running instance's window is raised and focused
- **A second launch with no URL still raises the window** rather than doing nothing visible
- The channel is started **after** the lock is won, asserted — a channel started first would
  reintroduce the design `P2PLAN-R5` withdrew
- A second launch when the channel is unreachable — the owner is alive but wedged — still refuses
  rather than hanging, within a stated timeout
- Verified on both platforms. **`OPS-005` amended 2026-08-01:** hosted Windows carries the Windows
  gate while `STARBASE` is unreachable, so `check (windows-latest)` satisfies this and the desktop
  slice stays with `STARBASE` for first release
  *(This read "`STARBASE` included" without qualification, which after the amendment demanded a
  machine nobody could reach for a criterion hosted Windows had already met — `T087-R4`.)*: the named-pipe and Unix-socket halves are
  different system calls

#### Out of scope

- Anything that makes the channel decide ownership (`ARC-006` amendment)
- Multi-user or networked access (`A-004`)

---

### T-048 — Verify the first real data migration when one is written

**Status:** Proposed — **not schedulable yet.** No migration transforms data.
*(Premise re-checked 2026-08-06 after `T169-R5`. Still true, and narrower than it was: `0009`
**destroys** data rather than transforming it. That is a different problem with a different answer
— it needs a test proving the rows are gone, which it has, not an allowance for values that
legitimately changed, which is what this task is for. What did move is the strict per-column rule
below: it now covers `jobs` only, because `history` no longer exists to compare.)*
**Owner:** Implementer, when the first data migration is authored
**Priority:** Medium at that point; nothing to do before
**Phase:** unassigned
**Depends on:** the first migration that changes stored values
**Relevant context:** `T014-R4`; `docs/project/TESTING.md` §7 (Migrations)
**Affected surfaces:** `tests/unit/test_persistence.py`

#### Scope

`T-014`'s migration test asserts strict per-column equality **for the tables in
`_MIGRATED_TABLES`**, which since 2026-08-06 means `jobs` alone. That is correct while every
migration either leaves a table's values alone or removes the table outright, and any unasked-for
change is loss. It will be **wrong** the day a migration legitimately transforms values.

**A destructive migration is not the case this task covers**, and `0009` is the reason to say so:
it removes rows on an explicit ruling and proves it with its own regression. This task is about the
opposite situation — values that change and are still correct — where equality has no way to tell a
good transformation from a corrupt one.

A `TRANSFORMED_BY_MIGRATION` allowance was written and then removed: `T014-R4` established that
an allowance can conceal a corrupt-but-readable migration, and an empty allowance protects
nothing while adding a mechanism nobody has exercised. Designing it against a real migration
beats designing it against an imagined one.

#### Acceptance criteria

- The first data migration ships with a test asserting the transformed values are **correct**,
  not merely different — a readable row holding wrong data is the failure mode `T014-R4` named
- Untransformed columns stay under strict equality
- The v1 fixture remains untouched; a new version freezes its own

#### Out of scope

- Any change to `T-014`'s current strict comparison, which is right until then

---

## Proposed — Phase 3

### T-190 — `docs/UX_SPEC.md` §6 still says its screen is unspecified

**Status:** Proposed — filed by `T-109`, 2026-08-07.
**Owner:** Planner / Documentation Maintainer
**Priority:** Low — no runtime behaviour depends on it; the defect is a current-truth document
stating a solved problem in the present tense, which is `T185-R1` exactly.
**Phase:** Phase 3 cleanup
**Depends on:** `T-109`'s verdict, so the correction describes what was approved rather than what
was submitted.

#### Scope

`docs/UX_SPEC.md` §6 carries a `[T]` clause reading *"This clause stays because `T-109`'s screen has
not been specified against the ruling yet"*, and a `P-16` paragraph asking whether `T-109` and
`T-111` share a screen as though it were open. `UX-007` ruled `P-16`, and the screen now exists:
`ui/options_dialog.py`, reached as `Options…` on the row's format control.

`AGENTS.md` §4 does not put `docs/UX_SPEC.md` in the Implementer's write set, which is why `T-109`
filed this rather than editing it.

#### Acceptance criteria

- §6's open questions read as ruled and built, in the past tense, with the built surface named.
- The `Save as preset…` clause describes the control **as built by `T-109`** (`T109-R5`), rather
  than saying it arrives with `T-111`. `T-111` still owns the other four operations.
- Nothing else in §6 changes: the ruled clauses are the contract the implementation was built
  against.

---

### T-191 — A queued row shows no size until it downloads

**Status:** Proposed — **filed 2026-08-08 by the `T143-R1` amendment**, which deferred pre-download
size here rather than declining it. A criterion cannot be narrowed into nowhere, so this is where it
went.
**Owner:** Implementer
**Priority:** Low — no defect, and no user has reported it. `UX-005` §3 does not promise a size
before a download starts, which is why `T-143` was amended rather than expanded
**Phase:** Phase 4 — polish, and it is a schema change, so it does not belong in a phase that is
exiting
**Depends on:** nothing
**Relevant context:** `T-143`, `T143-R1`, `UX-005` §3, `DAT-001`, `core/models.py` (`Job`,
`FormatInfo.filesize`, `FormatInfo.filesize_is_estimate`), `persistence/` migrations
**Affected surfaces:** `core/models.py`, `persistence/`, `ui/queue_view.py`, a migration
**Risk:** Low in mechanism, **Medium in honesty.** A size shown before a download is a *prediction*,
and `FormatInfo.filesize_is_estimate` exists because yt-dlp's own number is sometimes
`filesize_approx`. A row that states an estimate as a fact is the class of confident lie
`Job.progress` already refuses to tell

#### What is wrong

Nothing, today — and that is why this is Low. **No row of any kind shows a size before it runs.**
A pasted URL and a playlist entry are equally bare, so there is no inconsistency for a user to
notice; there is a field the application could show and does not.

`T-143`'s first acceptance criterion asked for it and could not have delivered it: a size lives
per-format in `FormatInfo.filesize`, and `Job` carries only `bytes_total`, which a *download*
reports. `T143-R1` found the criterion unmet, the maintainer amended it to the `UX-005` §3 anatomy,
and the deferred half is this entry.

#### Scope

Decide whether a queued row shows a predicted size, and if so store it. That means a field on `Job`
populated from the chosen format, a migration for it, and a decision on what the row says when the
number is `filesize_approx` rather than `filesize`.

**The estimate question is the real work.** Storing a number is a morning; deciding what a row says
when the number is a guess is the part that needs a ruling, because `REQ-003` already names the
column *"filesize/estimate"* and `T107-R7` made the two distinguishable for exactly this reason.

#### Acceptance criteria

- A queued row shows the size of the format it will actually download, before it downloads
- An estimated size is **shown as an estimate**, distinguishable from a size the site stated
- A format with no size at all leaves the row saying nothing rather than zero
- The stored size survives a restart, and a re-probe that changes the chosen format updates it
- Changing the format on a row changes the size it shows

#### Out of scope

- Predicting a size for a format the user has not chosen. The row shows what it will download

---

## Proposed — Phase 4

### T-301 — Four UI tests break when the application font grows by one point

**Status:** Proposed — found on 2026-09-08 while repairing the two that `ubuntu-latest` broke.
**Owner:** Implementer
**Priority:** Low — contained test debt with no user-facing evidence behind it. It is recorded so
the measurement is not lost, not because it blocks anything.
**Phase:** Phase 4 (test infrastructure; **not** a plan deliverable)
**Depends on:** nothing
**Relevant context:** `OPS-012`'s 2026-09-08 amendment, `tools/bigger_font_plugin.py`,
`tools/dialog_width_floor_probe.py`
**Affected surfaces:** `tests/ui/test_row_verb_wiring.py`, `tests/ui/test_add_dialog.py`
**Risk:** Low
**Required checks:** `ruff check .` · `ruff format --check .` · `pytest tests/ui` at the default
font **and** under `tools/bigger_font_plugin.py`

#### Scope

Four tests fail at one point larger than the default font:

```
tests/ui/test_row_verb_wiring.py::test_the_drawn_verbs_are_where_the_click_is_tested
tests/ui/test_row_verb_wiring.py::test_the_overflow_keeps_its_place_as_the_state_changes
tests/ui/test_row_verb_wiring.py::test_the_verbs_leave_the_message_its_width
tests/ui/test_add_dialog.py::test_the_menu_key_reaches_the_current_rows_menu
```

Three are one cluster — where verbs and the overflow land as a row narrows — and probably share a
cause. Reproduce with `PYTHONPATH=tools python -m pytest -q -p bigger_font_plugin tests/ui`.

#### Acceptance criteria

- For each, establish **product or test** by measurement, the way
  `tools/dialog_width_floor_probe.py` established the add-dialog floor. A pixel that moved is not
  by itself a defect, and an assertion that was only ever true at one font is not by itself sound.
- Repair whichever is wrong. **Do not loosen an assertion to reach green** — the two repaired on
  2026-09-08 were re-expressed as the property each was actually protecting.
- Record what a larger font does to verb placement, whichever way it goes.

#### Out of scope

- **Wiring the font lever into CI.** Gating on a standard nobody has established the product meets
  would leave the board red for a known reason, which is what removed the `STARBASE orphans` job.
- The other UI tests. **A 45-failure figure recorded earlier that day was wrong** — the lever that
  produced it did not restore the font between tests, so it compounded a point per test. At a true
  one point the count is four, and every accessibility-sounding test named in that figure passes.

<a id="t-302"></a>

### T-302 — Nothing detects orphaned workers automatically on either platform

**Status:** Proposed — the gap opened 2026-09-08 and is recorded rather than accepted silently.
**Owner:** Implementer, with the maintainer for where a scan is allowed to run
**Priority:** Medium — process lifecycle and orphaned workers are the first item in
`TESTING.md` §14's standing risk focus, and there is now no automatic signal for either.
**Phase:** Phase 4 (operations; **not** a plan deliverable)
**Depends on:** nothing
**Relevant context:** `OPS-012` as amended 2026-09-08, `OPS-010`, `docs/RUNNER_ORPHANS.md`,
`tools/orphan_scan.py`, `T-268`, `T-272`
**Affected surfaces:** `tools/orphan_scan.py`, possibly a local hook or schedule; **not**
`.github/workflows/` unless the maintainer rules otherwise
**Risk:** Medium — a detector that runs where orphans do not accumulate is worse than none,
because it reports a clean zero
**Required checks:** whatever the design needs; a **known positive** before any clean result is
trusted (`2026-08-29-orphan-scan-known-positive-soak.md` is the precedent)

#### Scope

`STARBASE orphans` was removed 2026-09-03 because it found `T-268`'s seven preserved specimens
every night and correctly failed, leaving the board permanently red. `Linux orphans` stopped on
2026-09-08 when `LINUX_RUNNER` was deleted and `kirk` and `Spock` were unregistered.

**Restoring either is not the answer, and this task exists because the obvious fix is unavailable.**
A hosted runner's VM is destroyed after every job, so a scan there finds nothing by construction.
Putting a self-hosted Linux runner back would undo the exposure reduction the maintainer chose the
same day.

#### First measurement, 2026-09-09 — not from clean suite runs on this machine

`tools/t302_orphan_accumulation_sampler.sh` ran nine rounds on `Spock` over two hours: a full
`tests/integration` + `tests/ui` pass each round, then two scans, at age 0 and again 90 seconds
later. **Nine suite exits of `0`, nineteen scans, no orphan reported**, with the known positive
passing first so that zero can be read. Rounds 5 to 9 ran alongside a live application session,
which the record treats as a property of the evidence rather than noise.

[The record](evidence/2026-09-09-T302-orphan-accumulation-sampling.md) states its own limits: a
run that exits cleanly is not the route that orphaned `T-268`'s specimens, two hours is not a
distribution, and the scanner only sees a process whose parent died. **So the first criterion is
answered by elimination rather than satisfied**, and the remaining candidate is a session that
ends badly — the shape `2026-08-27-T212-ytdlp-update-double-free.md` recorded.

#### Acceptance criteria

- Establish **where orphans actually accumulate now** that Linux CI is ephemeral. The working
  assumption was a developer's own machine; the 2026-09-09 sampling rules out clean suite runs on
  one, and the next measurement belongs on a session that ends badly rather than on more rounds of
  the same.
- Propose a detector that runs there — a pre-push hook, a periodic local run, or a documented
  manual step — and say plainly what it does **not** cover.
- **Prove it sees a known positive before any clean result is reported.** A blind scan prints the
  zero the author wanted.
- Do not reintroduce a nightly job that fails on known specimens; that is the shape `2026-09-03`
  removed.

#### Out of scope

- Reversing the runner move.
- `T-268`'s seven preserved specimens, which remain its own.

### T-212 — The recorded checklist run: the built window against the agreed flow

Historical evidence relocated 2026-09-08:
[Additional historical evidence](COMPLETED_TASKS.md#t212-validation).

**Carries one row by maintainer direction, 2026-08-13:** the **deferred panel mount**. `T-221` was
closed on a real-display observation — the maintainer did not see the one-turn transient — and the
maintainer directed that it be re-checked by hand in this pass rather than left as an open task.
One observation on one machine is evidence about that machine; this run is where a second is taken
deliberately, in front of the whole built window, and **recorded** in `docs/project/evidence/`. Both panel
kinds, since `T-209`'s audit found both spend that turn at 190×26.

**Status:** Proposed — filed 2026-08-09, owning the exit criterion the maintainer added the same
day; **the checklist half is written**, 2026-08-16, at `docs/PHASE_4_CHECKLIST.md` — before the
run, which is this task's first acceptance criterion. **Forty-eight** rows across seven sections
— counted; forty-seven when written, after the entry first said forty-one from an estimate, and
`6.1a` added 2026-08-28 with `T-292` — derived from
`docs/UX_SPEC.md` §2/§3/§8/§11/§12 and the accepted criteria of every surface Phase 4
added or reshaped, in `docs/CRITERION_8_CHECKLIST.md`'s shape and under its guards: rows say what
a user should see, task ids are back-references, and a failed row becomes a task entry rather than
an inline repair. The maintainer-directed panel-mount row is **5.6**, covering both panel kinds.
**What remains is the run itself** — a real display and a person looking at it — recorded in
`docs/project/evidence/` at a named head. A **run sheet** is published for the sitting, generated *from* this
file so the two cannot drift: it marks each row pass / fail / not run, keeps the marks per head,
and emits the `docs/project/evidence/` markdown to paste back. The criterion had no owner in the map above, which is exactly the
failure that map exists to surface.
**Owner:** Implementer
**Priority:** High — it is a phase exit criterion, and the phase cannot exit without the evidence
**Phase:** Phase 4 — **last.** The plan's own criterion text says why: a run taken before the
phase's surfaces land checks an application that is about to change.
**Depends on:** `T-146`, `T-195`–`T-202`, and the add-dialog chain — `T-203`, `T-204`'s
corrections (`T-207`, `T-209`, `T-210`, `T-211`) and whatever `T-208`'s investigation changes.
**Relevant context:** `IMPLEMENTATION_PLAN.md` §Phase 4 exit criteria; Phase 2's criterion 8 —
`docs/project/evidence/2026-08-05-criterion-8-checklist-run.md` and its two successor runs; `P2EXIT-R10`,
`P2EXIT-R12`; `docs/UX_SPEC.md`
**Affected surfaces:** `docs/project/evidence/` (the recorded run) and new task entries for what it finds
**Risk:** Medium — not that the run is hard, but that it is treated as a formality. Phase 2's
first run found **eleven defects against 2153 passing tests, none reported by any gate**, and
needed two further runs to reach 40 of 40

#### Scope

The criterion reads: *"The built window matches the flow that was agreed — evidenced by a recorded
checklist run against the running application, in `docs/project/evidence/`, the way Phase 2's criterion 8 was
evidenced."* This task writes the checklist, runs it against the running application, records the
run, and files what it finds. The checklist derives from `docs/UX_SPEC.md` — the agreed flow — plus
the accepted criteria of the surfaces this phase adds: the settings screen and its panes, the
reshaped add-dialog row, and the phase's queue and error-presentation changes.

**A walked-through session is not evidence.** `P2EXIT-R12` was a checklist claiming a pass over its
own recorded failures, and `P2EXIT-R10` was the same row claimed met and reset twice. The recorded
run is the deliverable; the pass is only what it hopefully shows.

#### Acceptance criteria

- **The checklist is written before the run**, derived from `docs/UX_SPEC.md` and the phase's
  accepted task criteria, and covers every surface Phase 4 added or reshaped
- **The run is recorded in `docs/project/evidence/`**, item by item, pass or fail, at a named commit — the
  format Phase 2's criterion-8 runs established
- **A failed item becomes its own task entry**, filed rather than repaired inline and re-claimed
  within the same run
- **A re-run after corrections repeats the whole checklist**, not only the failed rows — Phase 2
  needed three runs, and each was complete
- **The evidence names the commit and states that every depended-on task above was integrated at
  it** — a run over a tree still missing one of them is the "about to change" application the plan
  warns against

#### Out of scope

- **Fixing what the run finds.** Each finding is its own filed task with its own review
- **The Windows half.** `OPS-003`: there is no Windows machine, so the run is Linux; the
  pre-release Windows session inherits the same checklist, and the gap is named the way the plan's
  screen-reader split names its Narrator gap

### T-286 — The container section says what recode costs and never what it is for

**Status:** Proposed — **filed 2026-08-27 during `T-212`'s run**, from the maintainer's question:
*"Does re-encoding provide any tangible benefits over remuxing the files? Seems like the option is
pointless."* **It is not pointless, and the fact that the dialog left that question open is the
defect** — the note beside the radios states the cost of recoding and never the case that buys it.
**The option stays**; this task changes what the dialog says about it.
**Owner:** Implementer
**Priority:** Medium — a control whose purpose has to be reasoned out from first principles is one
users either avoid or misuse, and both cost a whole re-encode to discover
**Phase:** Phase 4 (polish; **not** a plan deliverable)
**Depends on:** nothing. `T-285` narrows *which containers* are offered; this changes *what the
section says* about the two verbs, and neither blocks the other
**Relevant context:** `ui/options_dialog.py:402`–`:431` — the three radios and the note;
`REQ-010`; `T-109`; `core/presets.py`, where the mp4 preset's selector already answers the common
case without any conversion at all
**Affected surfaces:** `ui/options_dialog.py`, `tests/ui/test_options_dialog.py`
**Risk:** Low

#### What is wrong

The note reads, in full:

> Remuxing keeps the streams and is quick; recoding re-encodes them and is not.

Both halves are true and the sentence describes only cost. A user reading it learns that one
option is slower and nothing about when the slower one is the right answer — which is why the
question this task was filed from is the reasonable conclusion to draw from the dialog as it
stands.

**Measured with ffmpeg 2026-08-27**, a one-second `vp9 + opus` webm and a one-second `h264 + aac`
mp4, plus a ten-second 640×480 clip for the cost:

| Operation | Result |
|---|---|
| **Remux** webm (vp9/opus) → mp4 | **Succeeds — and the output still contains `vp9 opus`** |
| **Remux** mp4 (h264/aac) → webm | **Fails**: *"Only VP8 or VP9 or AV1 video and Vorbis or Opus audio … are supported for WebM"* |
| **Recode** webm (vp9/opus) → mp4 | **Succeeds, producing `h264 aac`** |
| Cost | remux **0.11 s**, recode **4.86 s** — and the recode's output was **larger** than its source, 221 KB against 158 KB |

**Remux changes the wrapper; recode is the only thing that changes the codecs.** That is recode's
entire benefit and it is a real one: a source published as VP9 or AV1 only — which YouTube
increasingly does above 1080p — has no route to a file that plays on hardware speaking h264/aac
except through a re-encode.

**And it is narrower than it looks in this application**, which the note should not overstate
either: the mp4 preset already selects `bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]`, so
the common case is answered by *choosing* an h264 stream rather than by making one. Recode earns
its place only where no such stream exists.

#### Acceptance criteria

- **The section names the case recoding is for**, in the same register as the rest of the dialog —
  a user's words, not codec names, and one line rather than a paragraph
- **It does not oversell it**: the note must not read as advice to recode, given that format
  selection answers the ordinary case without one
- **The cost stays stated.** The present sentence is not wrong and the slowness is what stops a
  casual click; this adds the missing half rather than replacing the sentence
- **The wording is asserted by a test**, the way the dialog's other fixed strings are, so it cannot
  drift back into cost-only

#### An open question this raises, and does not answer

**A remux to `mp4` that leaves VP9 inside is a success that did not do what the user meant.** The
first row of the table is exactly the trap the maintainer's question was circling: the mux
succeeds, the extension changes, and the file still will not play where it was converted to play.
Whether the application should say anything about that is a real decision and **not part of this
task** — warning about it means the container section starts reasoning about codecs it does not
currently touch, and the honest alternative is that this is correct ffmpeg behaviour a
general-purpose tool need not editorialise. **Filed here so the observation is not lost with the
conversation; it needs a ruling before it needs a task.**

#### Out of scope

- **Removing recode.** It is the only route to a playable file from an AV1-only or VP9-only source
- **Which containers are offered** (`T-285`)
- **Choosing codecs**, or any control over the recode's encoder settings — `REQ-010` does not offer
  them and this task does not add them

### T-290 — Offer the yt-dlp update as recovery, not as a setting

**Status:** Proposed — **filed 2026-08-27 to build `OPS-002`'s amendment of the same day**, which
the maintainer ruled during `T-212`'s run: the override stays, and stops being a standing choice.
**Owner:** Implementer
**Priority:** Medium — nothing is broken today; what changes is which version the population runs,
and that compounds quietly in the other direction
**Phase:** Phase 4 (polish; **not** a plan deliverable). It is a presentation change to a screen
this phase built, and the maintainer may prefer it after the exit — that placement is theirs
**Depends on:** nothing. `T-289` crashes in this screen's update path and is a different defect;
neither blocks the other, but both touch `show_ytdlp`
**Relevant context:** `OPS-002` and its 2026-08-27 amendment; `ui/settings_dialog.py:1387` and
`show_ytdlp`/`show_ytdlp_problem`/`show_ytdlp_busy`; `REQ-025`; `NFR-007` — the update performs an
outbound download and must stay explicit, never automatic and never silent
**Affected surfaces:** `ui/settings_dialog.py`, wherever a download failure is presented, and
their tests
**Risk:** Medium — the honest version of this needs a route from a *failure* to the update, and a
failure surface that starts giving advice is how a row's anatomy grows a second voice (`T-243`)

#### What changes, and what does not

**Unchanged:** the pinned baseline, the user-managed copy resolved ahead of it, the version shown
in the UI, and revert as one action. The mechanism is not what was ruled on.

**Changed:** the update is currently `Update to the latest version` — a button of equal weight
beside `Use the bundled version`, in a Settings section that reads like every other setting. That
presentation invites a population onto versions this project has never tested. The amendment makes
it the way out of a site that has broken.

#### Acceptance criteria

- **The Settings screen no longer presents updating as a routine choice.** What it becomes —
  reworded, de-emphasised, moved behind a disclosure, or left in place with different words — is
  the implementer's proposal and the maintainer's ruling. **It must not disappear**: `OPS-002`
  requires the resolved version to be visible and revert to be one action, and both are still true
  after this
- **There is a route from a failed download to the update**, worded as what it is: sites change,
  and a newer yt-dlp may fix this one. This is the half that makes the reframing honest rather than
  merely quieter
- **That route does not turn the failure surface into an advice column.** `T-201`'s error anatomy
  and `T-243`'s one-voice rule both apply: a failure states what happened, why, and one next step —
  and a class with no honest next step still gets none
- **The offer appears only where it could be true.** A refusal that has nothing to do with the
  extractor — an unwritable folder, a full disk — must not suggest updating yt-dlp. `UX-005` §5
- **`NFR-007` is untouched**: still explicit, still never automatic, still never silent
- **The wording is asserted by tests**, the way the screen's other fixed strings are

#### Out of scope

- **Removing the override.** Explicitly rejected in the amendment; `OPS-002`'s *"pin only"*
  alternative stands refused, and more firmly while no release pipeline exists
- **Automatic or background update checks.** `NFR-007`
- **The crash in this path** (`T-289`)
- **Whether the application itself should self-update**, which `REL-001` leaves open and which the
  amendment names as the condition for reopening `OPS-002`

## Proposed — Phase 4.5

### T-184 — The escape hatch: additional yt-dlp options, parsed and bounded

**Status:** Proposed — filed 2026-08-07 with the phase. **Unblocked 2026-08-21**: `SEC-005` ruled
`--legacy-server-connect`, the one disposition this waited on (`T183-R3`, the sixteenth option the
audit surfaced), and **`unruled` is now 0** — every documented option has a class, which is the
condition a final refusal list needs. The three `SEC-003` corrections `T-256` also carried were
non-blocking and were ruled the same day; two of them **add** to this list. `T-183` delivered the
classification and `SEC-004` ruled the original fifteen forbidden, so the refusal list is the
audit's `app:sets` + `app:contained` + `app:plumbing` + **`app:policy`** + `excluded` classes —
**92 documented options**, up from 89 by `--legacy-server-connect`, `--netrc-cmd` and
`--client-certificate-password`. **Nothing in this phase starts before Phase 4 exits**, so this is
unblocked rather than startable.

**`Depends on:` is satisfied rather than removed.** `T-256` is still In Review; what it owed this
task is taken, and a reviewer disposing `T-256` differently would reach this line.

**The refusal list is 92 and this entry gave two numbers** (`T256-R2`). Its `Depends on:` line still
carried the pre-ruling **89**, so an implementer could read both the three newly refused options and
the old list that omits them — from the same entry. **92 is the live figure**, and 89 survives below
only inside the struck dependency, as what it was.

*(**This entry said "both blockers are cleared", "nothing outstanding" and "79 documented options",
and required a destination-keyed refusal, after `T183-R1`…`R5` had changed all four.** The
re-review found it: correcting the audit and leaving the task that consumes it is how an
implementer follows a specification the audit no longer holds — and it would have refused a safe
normalized value as though it were the `SEC-003` bypass.)*
**Owner:** Implementer
**Priority:** High within the phase — it is what makes `REQ-030` true before the typed fields exist
**Phase:** Phase 4.5
**Depends on:** ~~**`T-256`** — **one** unruled option, `--legacy-server-connect`~~ — **satisfied
2026-08-21 by `SEC-005`**. *(This said "sixteen unruled options and three `SEC-003` corrections"; fifteen were ruled by `SEC-004` and the three corrections are explicitly non-blocking — `T183-F1`.)* `T-183` delivered the classification, `SEC-004` ruled the original fifteen and `SEC-005` the sixteenth, with `SEC-003`'s amendment withdrawing two permissions; the refusal list is **92 documented options** across five refused classes, in `docs/YTDLP_OPTION_AUDIT.md`. *(This line said **89** while the status above said 92, so one entry gave both the pre-ruling and post-ruling list to whoever builds it — `T256-R2`.)* *(It also waited on `T-182`, which ruled on 2026-08-07: the refusal list starts with `-u`, `-p`, `--video-password`, `--impersonate`, `--xff`, `--exec` and `--exec-before-download` — `SEC-003`.)*

> **Four of `T-183`'s findings land here, and the first changes the design.**
>
>
> - **Finding 4 — the refusal list keys on the normalized value `parse_options` produces**, not on
>   the option string and **not on the `dest`**. Three suppressed spellings — `--geo-bypass`,
>   `--geo-bypass-country`, `--geo-bypass-ip-block` — reach the value `SEC-003` forbids under the
>   name `--xff`, so a list of strings enforces `REQ-EXCL-002` against one spelling in four. **But
>   `--no-geo-bypass` shares that same `dest` and normalizes to the value that *disables* the
>   bypass**, so keying on `dest` refuses a safe input. Run the candidate through `parse_options`
>   and refuse on what comes out. The refusal still names the string the user typed, because that
>   is where it is stated.
>
>   *(This bullet required destination-keying until `T183-R1`'s re-review. It was the audit's
>   original conclusion and it was wrong in the direction that looks safe.)*
> - **Finding 4, second half — decide the whole parser, not the documented part.** 36 suppressed
>   options have a `dest` no documented option has, so keying on `dest` does not reach them either.
>   Two are the forbidden family outright (`--exec-before-download`, `--no-exec-before-download`).
> - **Finding 6 — `--write-thumbnail` shares `writethumbnail` with the application.** It is the one
>   place a typed control has to share a key rather than own it; `T-249` owns the tri-state and the
>   merge rule is this task's.
> - **Finding 7 — five hatch options touch `T-046`'s reservation, unmeasured.** `--continue`,
>   `--no-continue`, `--part`, `--no-part` and `--post-overwrites` all change how yt-dlp treats a
>   file already at the target path, and the download session leaves a zero-byte reservation there.
**Relevant context:** `REQ-031`, `ARC-010`, `REQ-009` (the pattern), `T-034` (path containment),
`DAT-003` and `DAT-004` (redaction, and whose text this is), `ARCHITECTURE.md` §8 (a request is
frozen at job-creation time), `ARC-002` (it crosses a process boundary and must pickle),
`core/models.DownloadRequest`, `downloader/ytdlp_adapter.build_options`
**Affected surfaces:** `core/models.py`, `core/presets.py`, `downloader/ytdlp_adapter.py`,
`persistence/` (the request gains a field, so a migration), the preset/options UI, and their tests
**Risk:** **High.** It is a new route to two boundaries whose breach is Critical-band: writing
outside the chosen directory, and a secret in a log

#### Scope

An *Additional yt-dlp options* field, per preset and overridable per job, taking command-line
syntax, **parsed into a validated structure at job-creation time** and merged into `build_options`
under a stated precedence.

- **Parsed, not passed through.** The stored field is declared, typed, frozen and picklable like
  every other member of `DownloadRequest`; an unparsed string handed to yt-dlp is not acceptable
  even as an intermediate step
- **Containment.** Options that redirect where files land go through `T-034`'s check, not beside it
- **Redaction.** Values are this application's text under `DAT-004` and are redacted as such
- **Refusal.** An application-owned or excluded option is refused **where the user typed it, with
  the reason** — never accepted and dropped
- **Precedence.** A typed field wins over the hatch for the same user-owned key, because it is the
  one with a visible control; an application-owned key is never overridable at all

#### Acceptance criteria

- A valid option typed into the field reaches yt-dlp, proved by the option dictionary the worker
  receives rather than by the download succeeding
- **The same intent expressed as a typed field and as a hatch option produces the same option
  dictionary** — the assertion that keeps two routes from meaning two things
- An option that would write outside the output directory is **refused or contained**, with a test
  that fails when the containment call is removed
- **No hatch value appears unredacted in any log**, under the existing redaction test extended over
  the parsed values — including the case where the option name is innocuous and the value is not
- An application-owned option and an excluded option are each refused at edit time with a stated
  reason, and a test asserts they never reach `build_options`
- A malformed field fails **at edit time**, not after the bytes are spent — the same rule
  `audio_quality` already follows and for the same reason
- The migration adding the field round-trips an existing queue, and an old row without it loads
- `requires_ffmpeg` still answers correctly for a post-processor the hatch installed
- Both mypy platforms, `ruff`, the model, adapter, persistence and UI tests are clean
- **The refusal list is keyed on the value `parse_options` produces**, and a test asserts that
  `--geo-bypass` is refused for the same reason `--xff` is **while `--no-geo-bypass` is not refused
  as a bypass** — it fails if the list is rebuilt on option strings *or* on destinations (Finding 4,
  as corrected by `T183-R1`)
- **All five refused classes are enforced**, `app:policy` included. It is 10 rows the application
  owns by behaviour rather than by setting a key, and a refusal list built from the other four
  omits every one of them
- **`--break-on-existing` and `--break-per-input` are measured, not assumed inert.** At the pin
  `_match_entry` can raise on the current item and this worker calls `extract_info` directly rather
  than through `YoutubeDL.download`, so the option can turn the current job into a failure. Keep
  them hatch-reachable only if that effect is visible to the user
- **Every option the parser accepts is dispositioned, suppressed ones included.** A test walks
  `create_parser()` and fails on an option that is neither refused, nor typed, nor hatch-reachable
  — the documented 250 are not the parser's whole surface
- **`--continue`, `--no-continue`, `--part`, `--no-part` and `--post-overwrites` are measured
  against `T-046`'s reservation**, not reasoned about: a test shows what each does to a job whose
  target path already holds the zero-byte exclusive-create file (Finding 7)
- **The `writethumbnail` merge is stated and tested** — the application sets it to embed and delete,
  `T-249`'s control sets it to keep, and one of them has to win by a written rule (Finding 6)

#### Out of scope

- Typed fields for individual options — those are `T-183`'s tasks
- yt-dlp **configuration files** as an input route. A config file is a second, invisible source of
  options and would defeat every check above; if it is ever wanted it needs its own decision
- Per-entry hatch options within a playlist — `T-110` owns per-entry anything

---

*(**The nine typed-field tasks, `T-247` … `T-255`**, filed 2026-08-16 by `T-183`, which is where
the option lists come from: `docs/YTDLP_OPTION_AUDIT.md`. **44 options over nine tasks** — the
typed class minus the 21 that already have a `DownloadRequest` field. Counted, and
`tests/unit/test_option_audit.py` asserts the partition, so a task that quietly grows or drops an
option fails a gate.)*

**The following is true of all nine.** Each still states its own `**Status:**`, because `T-096`'s
gate reads that line per entry and a shared one would exempt nine tasks from the check that six
review rounds exist to enforce:

- **Owner:** Implementer · **Phase:** Phase 4.5, filed 2026-08-16
- **Depends on:** `T-183` approved. **Not on `T-184`** — a typed field is a declared member of
  `DownloadRequest` and needs nothing from the hatch. Nine independent tasks, in any order
- **Relevant context:** `ARC-010` §1, `REQ-030`, `docs/YTDLP_OPTION_AUDIT.md`,
  `core/models.DownloadRequest`, `core/presets.py`, `downloader/ytdlp_adapter.build_options`
- **Affected surfaces:** `core/models.py`, `downloader/ytdlp_adapter.py`, `persistence/` (each new
  field is a migration), the preset and options UI, and their tests
- **Acceptance criteria, common to all nine.** Each option below becomes a declared, typed,
  validated, frozen and picklable member of `DownloadRequest` (`ARC-002`, `ARCHITECTURE.md` §8);
  **the value is proved to arrive by asserting on the option dictionary the worker receives**, not
  by the download succeeding — `T-012` produced five defects that were values computed correctly
  and then not acted on, and `T012-R5` two more where yt-dlp accepted a key and ignored it; a
  malformed value fails **at edit time**; the migration round-trips an existing queue and an old
  row without the field loads; every control is keyboard-reachable and screen-reader-labelled
  (`NFR-005`); `ruff`, both mypy platforms and the touched suites are clean
- **Risk:** Medium for all nine — breadth rather than depth, and `NFR-008`'s churn lands on each

### T-247 — Video selection: which items, how big, how old

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Priority:** High among the nine — playlist item selection is the most-asked-for of the 44
**Options (7):** `-I/--playlist-items`, `--min-filesize`, `--max-filesize`, `--date`,
`--datebefore`, `--dateafter`, `--max-downloads`
**Specific criteria:** `-I`'s range grammar is parsed and refused at edit time, not handed to
yt-dlp as a string; the three date options accept yt-dlp's own relative forms (`today-2weeks`) or
refuse them with the reason; `--max-downloads` interacts with the queue's own counting and the
interaction is asserted rather than assumed.

### T-248 — Filename shaping and the modification time

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (7):** `--restrict-filenames`, `--no-restrict-filenames`, `--windows-filenames`,
`--no-windows-filenames`, `--trim-filenames`, `--mtime`, `--no-mtime`
**Specific criteria:** **`T-034`'s containment check runs after these, not before.** All three
filename options change what yt-dlp writes, and `--trim-filenames` can shorten a name into a
collision; the containment and collision tests are extended over each, and a test fails when the
check is removed. `--windows-filenames` is asserted on **both** platforms — its whole purpose is a
platform difference, and a Linux-only assertion proves nothing about it.

### T-249 — The sidecar writers: description, info JSON and thumbnail files

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (7):** `--write-description`, `--no-write-description`, `--write-info-json`,
`--no-write-info-json`, `--write-thumbnail`, `--no-write-thumbnail`, `--write-all-thumbnails`
**Specific criteria:** every file these write lands inside the chosen directory, through `T-034`
rather than beside it. **`--write-thumbnail` shares `writethumbnail` with the application**
(`T-183` Finding 6): `build_options` sets it to embed and then delete, this control sets it to
keep, and the resolution is one written rule with a test — the control is tri-state (off, one,
all). **`--write-info-json` writes a file yt-dlp's own help calls personal information**, so
`DAT-003`'s redaction question is asked of it before it ships, not after.

### T-250 — Format depth: sorting, checking and the merge container

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (4):** `-S/--format-sort`, `--check-formats`, `--no-check-formats`,
`--merge-output-format`
**Specific criteria:** `--format-sort`'s field grammar is validated against yt-dlp's own accepted
fields rather than passed through; `--check-formats` costs a request per format and the format
table's probe budget is stated (`T-161`'s per-entry lesson); `--merge-output-format` and
`remux_container` are two ways to name a container and the precedence between them is written down.

### T-251 — Subtitle depth: automatic captions, format and conversion

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (4):** `--write-auto-subs`, `--no-write-auto-subs`, `--sub-format`, `--convert-subs`
**Specific criteria:** `--convert-subs` installs an ffmpeg post-processor, so `requires_ffmpeg`
answers true for it and the user is told **before** the bytes are spent (`REQ-024`); automatic
captions and real subtitles are distinguishable in the UI, because "no subtitles" and "no *human*
subtitles" are different answers.

### T-252 — Download tuning and the retry policy the settings screen shows

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (7):** `-N/--concurrent-fragments`, `--fragment-retries`, `--extractor-retries`,
`--socket-timeout`, `--download-sections`, `--live-from-start`, `--no-live-from-start`
**Specific criteria:** **the three retry knobs this task owns are presented as one policy**, not
three integers — and the entry no longer calls them *the whole* retry policy, because
`--file-access-retries` and `--retry-sleep` stay in the hatch (`T183-R4`'s wording point) —
`--retries` already exists and `ytdlp_adapter` carries a comment deferring `--fragment-retries`
here by name, so this task is where the difference between them stops needing a comment to explain.
`--download-sections` takes a time-range grammar that is parsed and refused at edit time.
`-N` interacts with the pool's own concurrency (`ARC-007`, `CONCURRENCY_MAXIMUM = 16`) and the
interaction is measured rather than assumed.

### T-253 — Network reachability: address family and politeness delays

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (4):** `-4/--force-ipv4`, `-6/--force-ipv6`, `--sleep-interval`, `--max-sleep-interval`
**Specific criteria:** `-4` and `-6` share yt-dlp's `source_address` and are mutually exclusive —
`DownloadRequest` makes that unrepresentable rather than validating it; `--max-sleep-interval` is
refused without `--sleep-interval`, which is yt-dlp's own rule, and it is refused at edit time.

### T-254 — SponsorBlock, opt-in per preset

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Options (3):** `--sponsorblock-mark`, `--sponsorblock-remove`, `--no-sponsorblock`
**Specific criteria:** **off by default, and the control says what enabling it sends.** `SEC-003`
permitted this and `NFR-007` was amended to name SponsorBlock as a third permitted destination
*conditional on the user enabling it*; a test asserts no SponsorBlock request leaves the process
while the option is off. The category lists are validated against yt-dlp's own. `--sponsorblock-api`
is **excluded** — `SEC-003` declined a configurable endpoint — and this task does not reopen it.

### T-255 — Per-extractor arguments

**Status:** Proposed — filed 2026-08-16 by `T-183`
**Priority:** Lowest among the nine — one option, and the most expert-facing of the 44
**Options (1):** `--extractor-args`
**Specific criteria:** the `IE_KEY:ARGS` grammar is parsed into a validated structure, never stored
as the string the user typed; an unknown extractor key is refused **with the reason** rather than
accepted and ignored, which is `T012-R5`'s defect exactly; values are redacted under `DAT-004` like
any other text this application supplies, because an extractor argument can carry a token.

---


## Blocked

### T-074 — The Windows suite segfaults intermittently while the result pump is delivering

**Status:** **Blocked — on `T-092`, 2026-08-20. Still undiagnosed, still not blocking Phase 1**
(`OPS-007`, maintainer risk decision 2026-07-29). Downgraded **High → Medium**.

**The dependency was always there; the entry just never said it.** This task's own text already
concluded that only a **recurrence carrying a dump** can supply criterion 2 — *a stack is not a
cause* — and arming `STARBASE` to capture that dump **is** `T-092`. Meanwhile `Depends on:` read
*"nothing"* and the entry sat under `## Ready`, which asserts somebody can pick it up and make
progress. **Nobody can.** Repetition is spent at **466 attempts** — this entry's 361 plus the 105
full-suite Windows runs counted on 2026-08-20, which are more of the same shape rather than a new
one — and the one plan that remained — accumulating clean Windows runs — was measured on 2026-08-20 and
**cannot discriminate**, because the pre-fix sample is equally clean.

**What this changes is the board, not the risk.** The residual `OPS-007` accepted is unchanged and
still accepted; the four criteria are still deliberately not rewritten; and **the detection is in
the code rather than in this entry** — a recurrence turns the `windows desktop` job red whether or
not anybody is holding this task open. What moves is the honest label: this is waiting on a
machine being armed, which is `T-092`, which is waiting on a person.

*(Filed as a correction rather than a re-triage: nothing about the defect changed on 2026-08-20.
What changed is that the last avenue this entry proposed was tried and recorded as insufficient,
which left `Ready` claiming work that does not exist.)* The faulting object of the access violation is
unknown, product-versus-harness is unresolved, and the crash has never been reproduced: the
recorded **0 in 36** deliberate full-suite runs, plus **0/15 at `35fc7ec`** (run `30478557533`,
post-`T-090`) — **51 full-suite runs** in total, with 60 clean runs of the crashing test and 250
clean in-process iterations beside them. **361 attempts, zero events**, across three shapes and two
heads.

**`T-128` is diagnosed as of 2026-08-04, and it was a *harness* defect** — a fixture teardown
dropping a `QObject` that still owned a running `QTimer`, so the dispatcher followed a pointer into
freed memory. Two core dumps and a sub-second reproduction establish it; `src/` is not implicated,
because nothing there reads `is_idle` and the application holds one manager for the life of the
process.

**The free-evidence strategy below was tried on 2026-08-20 and it does not work. The runs were
gathered; what they cannot do is discriminate.** Measured rather than assumed: **105 completed
full-suite Windows runs** on `STARBASE` between 2026-08-04 and 2026-08-20, **zero native crashes**.
Method, so it can be re-run: every `CI` run since the `T-128` teardown fix at `bd4dde8`, taking the
`windows desktop` job's **`Full suite` step conclusion** rather than the job's — 92 `success` plus
**13 `failure`**, and the 13 count because each one **ran to completion with an ordinary pytest
tally**, which a process death cannot produce. 22 `cancelled` and 14 `skipped` are excluded because
the suite did not finish; the 14 are `T-270`'s window, where the step never ran. **Four of the 145
runs are accounted for separately and were not in the first telling of this** (`T074-R5`): they have
no `windows desktop` job at all — `31080589319`, `31120246285`, `31956224066` cancelled, and
`32042191296` failed before it. 92 + 13 + 22 + 14 + 4 = **145**, and none of the four is a completed
run, so the 105 is unchanged.

**Why that settles nothing, and it is this task's own arithmetic that says so.** The pre-fix sample
was **0 events in 51 full-suite runs**. The post-fix sample is **0 events in 105**. *"If the crash
stops recurring"* cannot be observed as a change, **because it had already stopped recurring before
the fix landed** — there is no measured pre-fix rate to beat, so the comparison is undefined.

**What the 105 buys is a dated zero and nothing more, and the first version of this paragraph
claimed more** (`T074-R5`). It gave a rule-of-three **2.9% per-run ceiling**, which assumes
exchangeable trials sharing one underlying probability. **These runs do not share one.** They span
sixteen days and many heads: between `bd4dde8` and `06745fa` the manager and test-lifecycle
surfaces alone move by **2 886 insertions and 622 deletions**. **`T074-R1` had already ruled exactly
this** — samples from materially different heads are not one population, and it required exact-head
observations rather than a rate. *A rate quoted over a changing tree is the same error as a rate
quoted from four observations on different heads*, which is the sentence this entry has carried
since `T074-R1` and which I re-made from the other direction.

**The observation and the non-discrimination argument both stand**; only the ceiling is withdrawn.
Neither `OPS-007`'s accepted residual nor the Blocked-on-`T-092` disposition ever rested on it.

**This is `T238-R2`'s ruling arriving at a second task, and neither entry saw it coming.** That
finding replaced `T-238`'s criterion 6 because *"a larger clean sample cannot distinguish **the
guard worked** from **the crash was always this rare**"*. **The sentence transfers verbatim**: swap
*guard* for *corrected teardown* and it is the paragraph below. Two tasks proposed the same
instrument against the same class of defect, and one of them had already had it ruled out.

**So what would actually move this is `T-092`, and nothing cheaper.** Clean runs cannot supply
criterion 2; only a **recurrence with a dump** can, which is what `T-092` arms `STARBASE` to
capture. Until then the honest position is unchanged: the residual is accepted under `OPS-007`, and
**the accumulating-runs plan is recorded as tried and insufficient rather than left open as
available**.

*(The paragraph below proposed that plan and is kept, because it is what was tried. It was
reasonable when written — what it missed is that its own Status paragraph already recorded the
pre-fix sample as clean, which is the fact that makes it unable to discriminate.)*

**That is a lead here, and it is the strongest one this task has ever had.** The Windows crash
recorded above happened in
`test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget` — **the same file and the
same `manager` fixture** whose teardown `T-128` found at fault, with the same `ResultPump` thread
alive in the traceback. The corrected teardown is now on both platforms.

**It is still not established as the same defect, and the bar has not moved.** Windows produced an
access violation and `T-128` a SIGSEGV; this task's faulting object was never determined, so there
is still nothing to compare against; and *a stack is not a cause* — this task's own words, which
apply to the resemblance as much as to the stack. What can be done now is cheap and was not before:
**`STARBASE` runs the full suite on every push (`OPS-010`), so repeated green Windows runs against
the corrected teardown are evidence that costs nothing extra to gather.** If the crash stops
recurring there over a meaningful number of runs, that is the first positive evidence this task has
had; if it recurs, the harness fix is ruled out as its cause and that is worth just as much.

*(This block read "A candidate reproduction exists … `T-128` owns finding out". `T-128` has now
found out, and what it found does not implicate the product.)*

**The four acceptance criteria below stay unmet, deliberately not rewritten.** All four presuppose
a deliberate reproduction, which is the one thing no instrument has produced, so `OPS-007` accepts
the residual rather than redefining the bar. `T-092` arms `STARBASE` to capture a crash dump so a
recurrence supplies criterion 2 — *a stack is not a cause* — instead of another anecdote.

*(This read "Ready — still undiagnosed and still blocking Phase 1" until `OPS-007`. Before that it
read "In Review — diagnosed and fixed", which `T074-R4` found unsupported; what was fixed is
`T-090`, and `T-090` is **not** established as this crash's cause — the pre-fix sample was equally
clean, so a clean post-fix run carries no causal weight.)*

**A separate defect was found on the way and is `T-090`.** The `T-038` log listener could be left
reading a queue that something else had closed — a real race on the same thread the crash
traceback names, now fixed with tests. **That is not this task.** Calling it "diagnosed and fixed"
claimed a causal link to the historical access violation that no evidence supports, which is what
`T074-R4` reports. This task's acceptance criteria remain unmet.

*(Superseded, and worth keeping: this block read "diagnosed and fixed" on 2026-07-29. Finding a
real defect near a crash is not the same as finding the crash's cause, and the wording did not
keep them apart.)*
`0/12 at ea53c71` (run `30429327464`). That is evidence against the original 25% anecdote and is
**not** a rate: the four original observations came from materially different heads, so they are
not one population, and a single event gives no bound worth quoting (`T074-R1`). The faulting
object is unknown, product-pump versus harness is unresolved, and there is no correction mutation.
**Phase 1's Windows criterion stays unverified.** *(This block claimed "1 in 16, not 1 in 4"; that
promoted samples from changed heads into a stable rate.)*
**Owner:** Implementer
**Priority:** **Medium** — downgraded from High by `OPS-007`. It is still an access violation in a
module under `src/`, in the suite `OPS-005` and `T-073` made Phase 1's only Windows gate; what
changed is that 361 attempts produced no reproduction, so there is no work left that repetition can
do. It returns to High the moment it recurs
**Phase:** Phase 1
**Depends on:** **`T-092`** — which is itself Blocked on somebody at `STARBASE`. The Windows
runner exists; what does not exist is a configured crash dump, and without one a recurrence
produces another anecdote rather than criterion 2
**Relevant context:** `T-073`, `OPS-005`, `ARC-002`, `src/tracks_and_trails/downloader/result_pump.py`
**Affected surfaces:** unknown — `downloader/result_pump.py` and/or
`tests/integration/test_manager.py`
**Risk:** **High to leave.** An intermittent crash makes every green Windows run mean less than it
appears to

#### Scope

The full suite on `STARBASE` died with exit **139**:

```
tests/integration/test_manager.py::test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget
Windows fatal exception: access violation
Thread 0x00000c88 [ResultPump] (most recent call first):
Thread 0x000024dc [Thread-50 (_monitor)] (most recent call first):
  File "...\tests\integration\test_manager.py", line 1028 in
    test_a_worker_that_ignores_cancellation_is_killed_inside_the_budget
Segmentation fault
```

**It is intermittent, and the evidence for that is unusually clean.** The failing run was
`30416495270` at `454b80e` — a **documentation-only** commit whose code is byte-identical to
`38650dd`, which had passed the same suite minutes earlier.

| Run | Head | Full suite |
|---|---|---|
| `30415333608` | `c41e2ef` | pass |
| `30416156751` | `38650dd` | pass |
| `30416495270` | `454b80e` | **access violation** |
| `30416723791` | `32f9bd2` | pass |

**One in four**, with no code difference between a pass and the failure.

**Line 1028 is before the cancellation**, which narrows this usefully. It is
`assert spin(lambda: bool(recorder.progress), timeout=60)` — the wait for the *first progress
message*, three lines above `download.cancel()`. So the crash is not in the escalation path the
test is named for. It is in ordinary message delivery: `ResultPump` is a `QThread` emitting Qt
signals carrying Python objects from its `run()`, while the main thread sits in `spin()` calling
`app.processEvents()`.

#### What is not known

Everything about the cause. Recorded as a question rather than a hypothesis dressed as one:

- Whether the fault is in **product code** (`result_pump.py`, in `src/`, so `ARC-002`'s pump is a
  candidate) or in the **test harness** (fixture teardown ordering, a receiver outliving or
  predeceasing a queued emission).
- Whether it is specific to `child_ignoring_cancellation`, which is the one worker in the suite
  that deliberately refuses to stop, or reachable by any job.
- Whether it reproduces at all outside `STARBASE`. It has never been seen on Linux across many
  full-suite runs, but Linux has never been where this project's process faults show up.

#### Diagnostic progress, 2026-07-29 — two things narrowed, cause still unknown

**It does not reproduce on Linux.** Two attempts, both clean:

| Attempt | Result |
|---|---|
| The crashing test alone, 40 iterations | **40 passed, 0 non-zero exits** |
| `tests/integration/test_manager.py` entire, 5 runs | **5 × 71 passed**, no crash, no fatal exception |

That is a negative result and is worth exactly what a negative result is worth. It does **not**
clear Linux: `T-069` was ordering-dependent and failed only when one specific test ran first, and
the Windows crash happened inside a full-suite run, not a module run. What it does establish is
that the fault is not reachable by simple repetition of the failing test on this platform, so
whatever it is depends on the platform, on suite-wide ordering, or on both.

**The most obvious cause is already defended against, and this is the more useful half.** The
classic PySide6 access violation of this shape is a `QThread` object being destroyed while its
`run()` is still executing — and `ResultPump` emits `session_ended` from *inside* `run()`, so a
slot that dropped the last reference would do exactly that. It cannot: `_release()` in
`manager.py` refuses to drop a session while its pump is live —

```python
if session.pump_started and not (session.pump_finished or session.pump.isFinished()):
    return
```

— and `_sessions.pop()` is the only thing holding the pump. `_Session` even documents the two
moments as distinct: "the thread emits `session_ended` from inside `run()`." So the first
hypothesis anyone would reach for is not it, which is worth recording so nobody spends the
afternoon re-deriving it.

**Still open.** The crash traceback named two threads — `[ResultPump]` and
`Thread-50 (_monitor)`, which is `multiprocessing`'s — and the fault was at the wait for the first
progress message. Whether it is the pump, the queue read beneath it, the interaction between them,
or the harness remains unanswered. Nothing here should be read as narrowing it to product code.

#### The ordering hypothesis, tested — 2026-07-29

The earlier attempts ran the crashing test alone and its module. The Windows failure happened
inside a **full-suite** run, and `T-069`'s precedent is that suite ordering was the entire story,
so that was the remaining Linux hypothesis. Six deliberate full-suite runs:

| Attempt | Result |
|---|---|
| Crashing test alone, 40 iterations | 40 passed |
| `test_manager.py` entire, 5 runs | 5 × 71 passed |
| **Full suite, 6 runs** | **6 × 1401 passed, every exit code 0** |

**Linux is now exhausted as a route to this defect**, at least by repetition. Three shapes of
attempt, none of which reproduced it. That is not proof of a Windows-only fault — it is the
absence of a Linux reproduction after looking in the three places worth looking.

**So the measurement has to happen on the machine that shows it.** `.github/workflows/t074-repeat.yml`
runs the suite N times on `STARBASE` and reports a rate. Three things about it are deliberate:

- **Manual dispatch, in its own workflow.** `ci.yml` is a gate and runs on every push; this is an
  instrument. Folding it in would mean paying its cost on every push or making a gate
  conditional.
- **It does not stop on the first crash.** A rate needs every iteration attempted; stopping early
  turns it back into an anecdote.
- **It separates crashes from failures by exit code.** `pytest` exits 1 for a failing assertion.
  A crash takes the interpreter with it, so the code is a signal or an access violation — and
  `T-074` is not a failing assertion. Counting them together would let an ordinary red test
  inflate the crash rate.

"About one in four" came from four ordinary CI runs, where the denominator was however many times
the gate happened to run. This makes the denominator a choice, which is what the acceptance
criteria ask for.

#### The instrument ran — 2026-07-29, run `30429327464`

Twelve full-suite iterations on `STARBASE`, every one attempted:

| Iterations | Crashes | Failures |
|---|---|---|
| **12** | **0** | 0 — `1395 passed, 20 skipped, 32 deselected` each time, 209-217 s |

**"About one in four" was a denominator of four**, and this batch is not a replacement for it.
`0/12 at ea53c71` says the crash is not reliably reproducible at that head. It does **not**
establish a rate (`T074-R1`): the four earlier runs and these twelve are not one controlled
population — the manager and the full-suite composition changed materially between them, including
new integration tests — and after a single event an aggregate point estimate is not a bound. A
clean run is unremarkable under a 25% failure probability and under a 6% one alike.

The crash is real. It happened with a traceback naming `[ResultPump]` and `multiprocessing`'s
`_monitor`, on a documentation-only commit whose code was byte-identical to a passing run.

**It stays a Phase 1 blocker, and the reason is where it landed.** The only observed native crash
is in ordinary `ResultPump` delivery — the exact `ARC-002` path Phase 1 exists to prove — so the
uncertainty cannot be resolved in favour of product safety by counting clean runs. Downgrading it
or accepting the risk is the maintainer's explicit decision to record, not an inference this task
may draw.

**Still unknown: the cause.** Nothing here narrows it. A larger batch is running to either bound
the rate further or catch one with fresh diagnostics; the workflow keeps every iteration's output,
so a crash caught there arrives with its traceback rather than as a count.

*(Superseded: this section previously read "Not yet run. The job is authored and pushed;
executing it needs `STARBASE` and is the next step on this task." It has now run.)*

#### Diagnostic session, 2026-07-29 — narrowed, not diagnosed

**Both threads named in the crash are ours.** The traceback listed `[ResultPump]` and
`Thread-50 (_monitor)`, and `_monitor` was read as `multiprocessing`'s. It is not: `multiprocessing`
declares no such function, and `_monitor` is
`core/logging.py`'s `_ToWhicheverHandlersWeHaveNow._monitor` — the `T-038` log listener's thread
body. So the crash happened with the result pump and the **logging listener** both live, which
points somewhere the earlier notes did not.

**A mechanism worth testing, stated as a hypothesis.** `_monitor()`'s `finally` closes the worker
log queue — a `multiprocessing.Queue` — and `stop_listening_for_worker_logs()` **waits for
nothing**, deliberately (`T038-R2`, and it is right to: the GUI thread must not block on a slow
handler). So the close runs on the listener thread while parent threads may still be logging into
that queue and a spawned writer may still hold the other end. Closing a multiprocessing queue
under a concurrent user is the kind of thing that faults natively instead of raising, which is the
shape this crash took. The crashing test is also the one that **kills** a worker rather than
asking it to stop, so a writer dying mid-record is in scope there and almost nowhere else.

**Nothing here demonstrates that.** It is a mechanism that fits, and the file it implicates has a
recorded reason for the behaviour. It is written down so the next attempt starts from a candidate
rather than from the whole suite.

**What was attempted, and what it cost:**

| Attempt | Result |
|---|---|
| Repeat batch, 24 full-suite iterations on `STARBASE` | **0 crashes** (run `30454206697`) |
| Both batches together, recent heads | **0 in 36** |
| Repeat batch, 15 full-suite iterations at `35fc7ec`, **post-`T-090`** | **0 crashes, 0 failures** (run `30478557533`) |
| The crashing test alone, 60 iterations on Windows | **60 passed, 0 failed, 0 crashed** |
| A direct stress of the logging-teardown race | **unusable — it hung on Linux before its first iteration** |

The last row is the honest one. The harness drives a parent thread logging continuously while a
spawned writer is killed and the listener is torn down; it never reached a print, so it deadlocked
in its own setup rather than measuring anything. A failed instrument is not a negative result, and
it is recorded as neither.

**Classification is unchanged: product versus harness is still unresolved**, and `T-074` remains a
High Phase 1 blocker. What has changed is where to look — logging teardown alongside the pump,
rather than the pump alone.

#### What the diagnostic session produced — 2026-07-29

It found a **different** defect, now filed as `T-090`: the log listener could be left reading a
queue something else had closed. The evidence for that moved there with it.

**What it did not produce is anything about this crash.** The access violation has never been
reproduced — 0 in 36 full-suite runs, 60 clean runs of the crashing test alone, 250 clean
in-process iterations — so its faulting object is still unknown and it is still unclassified
between product and harness. `T074-R4`: a real race on the same thread is a candidate, not a
cause, and the crash's absence cannot distinguish them when it was already absent every time.

**What is genuinely narrowed** is that `_monitor` in the traceback is the `T-038` log listener
rather than anything in `multiprocessing`, so the next attempt has two of our own threads to
account for rather than one.

#### Acceptance criteria

- The failure is **reproduced deliberately**, with a rate, rather than waited for
- The faulting thread and the object it touched are identified — a stack is not a cause
- The fix is proven by a mutation that restores the crash, not only by runs that stop crashing
- If it turns out to be the harness rather than the pump, that is recorded explicitly, because
  the opposite conclusion is the one a reader would assume from the file it crashed in

#### Out of scope

- Retrying, `xfail`, or a rerun plugin. `T-069` established the rule: an intermittent failure gets
  its trigger found, not its symptom hidden. The one time this project reached for a retry the
  reviewer's instruction was explicit — *do not retry or xfail*
- `T-056`, which is a different intermittent on a different platform and is `OPS-005`-downgraded

---

### T-092 — Arm `STARBASE` so the next access violation leaves a cause, not a stack

**Status:** **Blocked — prepared 2026-08-01, on *somebody at* `STARBASE`.**

**Re-triaged 2026-08-04: still blocked, but it may no longer be the only route.** This task exists
because the faulting object of `T-074`'s access violation is unknown and a Windows crash dump was
the only way to get one. `T-128` records something in the same subsystem crashing on **Linux** at
roughly 2 in 39 — where a core dump needs `ulimit -c` and a pattern, not a person at a machine and
consent to write dumps on it. **That does not unblock this**, which is specifically about Windows,
and the two crashes are not established as one defect. It does mean the *cause* may become
obtainable without this task, which is worth knowing before anyone spends a trip to the desktop on
it.

Re-triaged 2026-08-03:
the machine came back that day and now runs every Windows job, so "blocked on `STARBASE`" no longer
says what it means. The three remaining criteria need a person to arm dumps, crash a process on
purpose and open the result — none of which a CI job does. **Availability was never the blocker.** The reviewer classified it
so on 2026-08-01: the safe correction is accepted (`T092-R1`) and the scope amendment is taken
(`T092-R2`), and **nothing further can be done from here.** Three criteria need somebody at the
machine.
*(This read "Ready — prepared 2026-08-01, and NOT complete", which put a task nobody could pick up
in the list of tasks to pick up.)* The maintainer's consent was given
2026-08-01 and the whole configurable half is committed: `tools/windows/crash-dumps.ps1` arms and
disarms it, `docs/WINDOWS_VERIFICATION.md` records the procedure and its disk cost, and both
`STARBASE` jobs collect a dump when one exists. **Three of the five acceptance criteria are
unmet and cannot be met from here** — they require running the script on `STARBASE`, crashing a
process on purpose, and opening the dump. See "Prepared, and what remains" below.
*(This read "Ready — the instrument `OPS-007` leans on".)*
**Owner:** Implementer
**Priority:** Medium — it buys nothing today and is the whole diagnostic plan if `T-074` recurs
**Phase:** Phase 1 origin; it is an instrument, not a deliverable, and gates no exit
**Depends on:** `STARBASE`, which exists. Needs the maintainer's consent to write dumps on a
machine they use
**Relevant context:** `OPS-007`, `T-074`, `T-073`, `docs/WINDOWS_VERIFICATION.md`
**Affected surfaces:** `docs/WINDOWS_VERIFICATION.md`, `.github/workflows/ci.yml` and
`t074-repeat.yml` (a metadata report, never a dump artifact), `STARBASE` machine configuration
**Risk:** Low to the product — it touches no source. The real risk is on the machine: dumps are
written unattended and a full-memory dump of a Python process with Qt loaded is not small

#### Scope

`T-074`'s second acceptance criterion is that **the faulting thread and the object it touched are
identified — a stack is not a cause.** `faulthandler` cannot supply that: it printed
`[ResultPump]` and `Thread-50 (_monitor)` and named neither the faulting module nor the address.
A minidump does.

So: configure Windows Error Reporting local dumps on `STARBASE` for the interpreter that runs the
suite, and have the `t074-repeat.yml` and `windows desktop` jobs **report** any dump written during
that run — name, size and timestamp into `reports/crashdumps.txt` — leaving the dump on the machine
for deliberate retrieval. Then a recurrence, in CI or in an ordinary run, produces something a
debugger can read instead of another anecdote.

*(**Superseded, and the wording matters because this is the live instruction.** This said "upload any
dump they find as an artifact", which `T092-R1` found unsafe on three counts: WER is keyed by
executable *file name* so the folder collects any `python.exe` under that account, nothing filtered
stale dumps so the deliberate proof dump would be re-uploaded on every later run and announced as a
recurrence, and a full memory dump can carry an unrelated program's heap into a CI artifact. The
metadata-only scope is the maintainer's decision of 2026-08-01 — `T092-R2`, which stayed open once
because the criterion was corrected and this sentence was not.)*

**Consent first, and this is not a formality.** `STARBASE` is the maintainer's own desktop.
`OPS-005` and `T-073` both carry the rule that a workflow must never provision it, and
`docs/WINDOWS_VERIFICATION.md` records what installing Python there already cost. Dump capture is
machine configuration and belongs in that document as a manual, reversible step — not in a
workflow.

#### Acceptance criteria

- A **deliberately crashed** Python process on `STARBASE` leaves a dump at a known path — proven by
  causing an access violation on purpose, not by trusting the registry keys
- That dump, opened, names a faulting module and address. If it cannot, this task has failed at the
  thing it exists for and says so rather than reporting the keys as success
- Dump size and retention are bounded and stated; the disk cost on a real machine is named
- **The jobs report a dump's existence and never upload it** — name, size and timestamp into
  `reports/crashdumps.txt`, with the dump left on `STARBASE` for deliberate retrieval. Both the
  "a dump was written" and "no dump" paths stay green: a missing dump is the normal case and must
  not redden the gate
  *(**Scope amended 2026-08-01, maintainer decision** — `T092-R2`. This read "upload a dump when
  one exists". WER is keyed by executable *file name*, so the folder collects any `python.exe`
  under that account and a full memory dump can carry an unrelated program's heap into a CI
  artifact; the old wording could not be met without reintroducing `T092-R1`. The narrower
  alternative — copy the interpreter to a distinct name and key WER to that — is recorded in
  `docs/WINDOWS_VERIFICATION.md` rather than taken, because it changes how the suite is
  launched.)*
- `docs/WINDOWS_VERIFICATION.md` records the configuration, how to undo it, and the disk cost

#### Out of scope

- Diagnosing `T-074` — this task cannot, and pretending otherwise is what `T074-R4` caught
- Any change to `src/`
- Dump capture on Linux, or on hosted runners, which are discarded anyway
- Making `T-074`'s recurrence more likely; this is passive capture, not a stress test

#### Prepared, and what remains, 2026-08-01

**Done, and committed:**

- `tools/windows/crash-dumps.ps1` — arms WER local dumps for `python.exe` under `HKCU` (no
  elevation, scoped to one executable rather than the whole machine), and `-Remove` undoes it.
- `docs/WINDOWS_VERIFICATION.md` — why, how to arm it, **how to prove it**, the disk cost, and how
  to undo it.
- `ci.yml`'s `windows desktop` job and `t074-repeat.yml` each stamp their start time and write
  `reports/crashdumps.txt` naming any dump written **during that run** — and upload no dump at all.
  `if: always()` and `continue-on-error: true`, because **no dump is the normal case and must not
  redden the gate**.
  *(This described copying the dump into `reports/`, which is what `T092-R1` found unsafe. The
  scope amendment above is the maintainer's, taken 2026-08-01.)*
- Full dumps (`DumpType 2`) rather than mini, stated with the cost: ~300–600 MB each for a Python
  process with Qt loaded, five kept, so up to ~3 GB. A mini dump routinely lacks the heap the
  faulting address points into, which is the entire question `T-074` is asking.

**Unmet, and honestly so** — each needs the machine:

| Criterion | State |
|---|---|
| A deliberately crashed process leaves a dump at a known path | **Unmet.** Nobody has run the script or the crash |
| The dump names a faulting module and address | **Unmet**, and it is the one that decides whether this task succeeded at all |
| Dump size and retention bounded and stated | **Met** — in `docs/WINDOWS_VERIFICATION.md` |
| The jobs **report** a dump and never upload one | **Half met.** The steps exist and both YAML files parse; no CI job has executed a step since 2026-07-30, so neither branch has run |
| `docs/WINDOWS_VERIFICATION.md` records config, undo and cost | **Met** |

**Why this is filed as prepared rather than done.** `T074-R4` caught this task's predecessor
reporting registry keys as evidence. The keys are not the evidence; a dump that names a faulting
module is. Until somebody runs the two commands in the document on `STARBASE`, the correct status
is that the instrument is *ready to arm* and has never fired.


#### Correction, 2026-08-01 — `T092-R1`

**The prepared upload was unsafe before it had ever run.** Three problems, all real:

- **WER is keyed by the executable's file name**, so `python.exe` collects *any* Python process
  under that account, not this project. There is no narrower WER key. A dump in the folder is
  therefore not by itself evidence of `T-074`, and the report now says exactly that.
- **Nothing cleared or time-filtered the folder**, so the deliberate proof dump — or a months-old
  one — would be re-uploaded on every later run and announced as a recurrence that never happened.
  Both jobs now stamp their start time and report only what was written after it.
- **A full memory dump can carry an unrelated process's heap**, and a CI artifact is a copy of it
  somewhere else. **Nothing is uploaded now.** The jobs write `reports/crashdumps.txt` with the
  dump's name, size and timestamp and leave the dump on `STARBASE` for deliberate retrieval.

`docs/WINDOWS_VERIFICATION.md` gains the provenance and disclosure reasoning beside the disk cost,
which is what it was missing. The narrower alternative — copy the interpreter to a distinct file
name and key WER to that — is recorded rather than done, because it changes how the suite is
launched.

**Three acceptance criteria remain unmet and still need the machine.** Nothing here changes that.

---

### T-068 — Qt writes a font warning to stderr on a real Windows machine

**Status:** **Blocked — on the runner question, which just got harder**, 2026-07-28; re-triaged
2026-08-03 and **again 2026-08-04, unchanged and verified**. `OPS-010` restored the Windows suite
to every push, which sounds like it would help and does not: it restored the **`STARBASE` desktop**
job, while `check`'s hosted Windows leg stays dropped. `vars.WINDOWS_RUNNER` is set, so hosted
Windows still does not run at all. The cost of answering this is now explicit — unsetting that
variable for one run spends hosted Windows minutes at a 2x multiplier, against a nearly exhausted
quota. The frozen half is now obtainable: `frozen windows` runs on `STARBASE`. The other half
asks *why the hosted runners never showed the fault*, and hosted Windows **no longer runs at all**
while `WINDOWS_RUNNER` points at the desktop (`docs/project/TESTING.md` §10). Answering it now needs that
variable unset deliberately for a run. A consequence of the gate rebuild, recorded rather than
discovered later. The
environment fix itself was not contested: the warning was the symptom, and the defect is that Qt
had **zero font families** under `offscreen` on that machine, so the whole offscreen UI suite ran
with no fonts. `QT_QPA_FONTDIR` is set before PySide6 is imported, is Windows-only, and honours an
explicit caller value. The task's own acceptance criteria still require the runner difference to
be explained and a Windows frozen artifact to be checked; both need a hosted runner. See
**Evidence**.

**No longer a Phase 1 exit dependency** (`OPS-005`, 2026-07-29). Still open, still Blocked. This
one runs the *other* way from `T-056`: the defect appeared **on** the real machine and the hosted
runners are the ones that look clean, so the fix is already validated where the fault was. What
remains is the diagnostic question of why the runners never showed it — worth answering, not worth
holding a phase for.
**Owner:** Implementer
**Priority:** Medium — an assertion about a *clean* run is failing, and the cause is not understood
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `T-007`, `tests/ui/test_app_launch.py`, `OPS-004`
**Affected surfaces:** `tests/ui/test_app_launch.py`, possibly packaging
**Risk:** Medium — unknown cause; it may be cosmetic, and it may be a deployment gap

#### Scope

`test_application_launches_and_exits_cleanly` asserts the application writes nothing to stderr on
a clean run. On `STARBASE` it writes:

```
QFontDatabase: Cannot find font directory <prefix>/PySide6/lib/fonts.
Note that Qt no longer ships fonts. Deploy some ... or switch to fontconfig.
```

**It fails in both the venv and the CI-style install**, so it is not the virtualenv — an
A/B that also corrects the implementer's first guess, which was that the venv caused it. The
cause is genuinely unknown and this task exists to find it rather than to silence it.

Two reasons not to treat it as noise. It only appears on a machine that is not a CI runner, which
is exactly the population `OPS-004` was written to stop assuming about. And a Qt that cannot find
a font directory under the offscreen platform raises an unanswered question about the **frozen**
artifact, which is what a user runs.

#### Acceptance criteria

- The cause is identified — not "PySide6 does that", but why this machine and not the runner
- Whether the frozen build (`T-020`, `T-033`) shows the same warning is answered on Windows
- If the warning is benign, the test says so deliberately rather than being loosened to pass
- If it is not benign, the fix is in packaging or startup, not in the assertion

#### Evidence, 2026-07-28

**The warning was the symptom. The defect is an empty font database.** Measured under
`QT_QPA_PLATFORM=offscreen` on `STARBASE`, in the interactive desktop session:

```
FAMILIES 0
SAMPLE  []
DEFAULT Sans Serif
```

Zero families. So the **entire offscreen UI suite** runs there against no fonts: every assertion
about a widget's size, about elision, or about anything else derived from font metrics is measured
against nothing — and passes. A suite that agrees with itself while measuring an empty font set is
the shape `docs/project/TESTING.md` §13 exists to catch, which is why this was not allowlisted into
`PLUGIN_NOISE` alongside `propagateSizeHints`. That allowlist is for artifacts that change no
measurement; this one changes every measurement.

**Not our code.** A bare `QApplication` produces nothing; a bare `QLabel` reproduces it in full,
with no project code involved. Same result in the venv and the no-venv checkout, which also
corrects the first guess recorded against this task — it is not the virtualenv.

**Not the session either.** It reproduces identically in session 2, so it is not an artifact of
running over SSH, which was the other plausible explanation and had to be ruled out because
several other results were.

**Fix:** `tests/conftest.py` sets `QT_QPA_FONTDIR` to `%WINDIR%\Fonts` on Windows, with
`setdefault` so an explicit value wins. Verified: `families()` goes from 0 to a populated list and
`test_application_launches_and_exits_cleanly` passes.

**Open, and it needs a runner:** *why the runners do not show this.* Their offscreen Qt evidently
finds fonts by some route this machine lacks, and until CI runs it is unknown whether
`QT_QPA_FONTDIR` changes anything there. If their database is already populated the variable is
ignored, which is the expected case — expected, not verified.

#### Out of scope

- Weakening the empty-stderr assertion to make the run green; that assertion caught this

---

### T-056 — `still_running` reports a reaped Windows process as alive, intermittently

**Status:** **Blocked — on a reproduction, not on a machine**, 2026-07-28 at `9c92c32`.

**Re-triaged 2026-08-04, and a candidate reproduction was checked and rejected.** The overnight
`-n auto` run failed exactly this task's subject —
`test_the_survival_check_can_tell_a_live_process_from_a_dead_one`, `still_running`'s own test — on
Linux, which looked like the reproduction this task has waited for since July. **It is not.** The
assertion was *"a running process was reported dead"*: `still_running([alive.pid])` returned `[]`
for a live process. This task is the **opposite** symptom — a *reaped* process reported **alive**.
Same helper, inverted direction, and a false negative under parallel load is a different defect
from a false positive on Windows.

Recorded rather than left for somebody else to find and re-check. What it does say is that
`still_running` has a second failure mode nobody had seen, which `T-123` carries.

Re-triaged 2026-08-03: `STARBASE`'s return does **not** help. This task already had its Windows
evidence and that is the finding — reverting the fix passes 20/20 there, so the defect does not
reproduce on the machine we have. More runs of the same machine cannot close it. The reviewer
found the implementation correct and could not verify it: the changed branch does not execute on
Linux, so neither the runtime behaviour nor the mutation that proves it can be observed here. The
helper decides by exit status on Windows and the third acceptance criterion is answered in its own
docstring.

**A Windows machine was not enough** (2026-07-28, `STARBASE`, Windows 10 22H2). The corrected
helper passes 3/3. Reverting it to the presence-based form it replaced passes **20/20** — the
defect does not reproduce here at all. A positive control (`still_running` always answering
"nothing alive") **fails** on the test's first assertion, so the patching mechanism is proven and
the survival is a real measurement rather than a mutation that never applied.

So the next step narrows rather than clears: this wants **`windows-latest`'s image**, Windows
Server, not Windows as such. `30323328299` remains the only observation of the defect anywhere.

**No longer a Phase 1 exit dependency** (`OPS-005`, 2026-07-29). Still open, still Blocked, but it
does not gate the phase: `still_running()` is test-only code that never ships, and its documented
sole error direction is a false **alive** — it can redden CI, it cannot make broken reaping look
correct. Windows Server is not a supported platform (`REQUIREMENTS.md`), so a finding seen only
there is a CI-reliability concern rather than a user-facing one.

**What that decision explicitly does not claim.** The mechanism is Windows-*general*: Windows has
no zombie state and a terminated process stays visible while any handle to it is open, which is
identical on Windows 10 and on Server. `STARBASE`'s 20/20 is therefore **absence of a trigger, not
evidence of correctness**. The risk is accepted on the error direction, not on the clean run.
**Owner:** Implementer
**Priority:** Medium — an intermittent failure in the helper every `T-019` assertion rests on
**Phase:** Phase 1
**Depends on:** nothing
**Relevant context:** `T-019`, `docs/project/TESTING.md` §7 (Cancellation, Worker crash)
**Affected surfaces:** `tests/integration/test_manager.py`
**Risk:** Medium — it decides whether the process-tree suite is telling the truth

#### Scope

`test_the_survival_check_can_tell_a_live_process_from_a_dead_one` failed once on `windows-latest`
in run `30323328299`: `still_running([dead_pid])` returned `[7208]` for a process the test had
already reaped. It passed on the runs either side, so it is **intermittent, not a regression** —
nothing in the `T-016` batch touches `process_tree.py` or that helper.

The likely cause is that `still_running` treats "psutil can still see the pid" as alive, excluding
only `NoSuchProcess` and `STATUS_ZOMBIE`. Windows has no zombie state, and a terminated process
stays visible while a handle to it remains open, so there is a window in which a dead process
reports as running.

**This matters more than a flaky test usually would.** `still_running` is the helper the whole
`T-019` descendant-reaping suite decides on, and its own docstring says a guard nobody watches
fail is the shape `docs/project/TESTING.md` §13 exists to catch. A false *alive* fails loudly, as here; the
concern is whether the same imprecision can produce a false *dead* and make a reaping assertion
pass without anything having been reaped.

#### Acceptance criteria

- The helper distinguishes a running process from a terminated-but-visible one on Windows, by
  exit status rather than by presence
- The claim is demonstrated on Windows CI, not reasoned about from Linux
- Whether the previous form could report a live process as dead is answered explicitly, and the
  answer is recorded rather than assumed benign

#### Out of scope

- Changing `downloader/process_tree.py`, which is `T-019`-approved and not implicated

#### Evidence, 2026-07-28

**The fix is Windows-only, because the imprecision is.** On POSIX the terminated-but-visible state
*is* the zombie state, so `status()` was already asking the right question. On Windows there is no
zombie and a corpse stays visible while any handle to it is open, so the helper now uses
`wait(timeout=0)` there — `WaitForSingleObject` on psutil's own handle, which neither disturbs
anyone else's handle nor depends on visibility.

**The first attempt used `wait(timeout=0)` on both platforms and broke the suite**, which is worth
keeping: on POSIX that call is `waitpid`, so inspecting a worker *reaped* it and stole the exit
status `multiprocessing` was waiting for. `is_alive()` then never reported the process gone and
the manager never went idle —
`test_cancelling_a_download_kills_what_the_worker_spawned` failed exactly that way. A survival
check that changes what it observes is worse than an imprecise one.

**The third criterion is answered, not assumed benign.** The previous form could **not** report a
live process as dead: it answered "dead" only on `NoSuchProcess` (and `ZombieProcess`, its
subclass) or on a `STATUS_ZOMBIE` a live process never has, and `AccessDenied` was uncaught and so
would have failed loudly. Its one error direction was **false alive**, which fails an assertion in
the open rather than letting a reaping assertion pass over nothing. The answer is recorded in the
helper's docstring, where the next reader of the helper will find it.

**The test now drives the failing shape**: a third process is killed and deliberately *not* waited
on. On Linux that is a zombie, which the old form already handled; on Windows it is exactly run
`30323328299`'s failure.

**Mutations run:** answering by presence alone everywhere — killed. Reporting nothing as alive —
killed. **Disabling the `win32` branch so it falls back to the POSIX question — survived, and
cannot do otherwise here**: the branch is unreachable on Linux by construction. That is
`AGENTS.md` §8's "a host-only check is not the whole gate" in its exact form, and it is why this
task is not claiming to be done.

**Checks:** `ruff check .`, `ruff format --check .`, configured `mypy` and `mypy --platform win32`
(72 files each — the win32 scope is what analyses the new branch at all) all pass. Bare `pytest`
green.

**Blocker:** the Windows demonstration. This machine has no Windows and the branch cannot execute
here, so approval needs the `windows desktop` job to run the corrected helper and the third
mutation against it. Same shape as `T-033`'s blocker: the code is done, the evidence is not
producible locally.

---

### T-039 — Verify Windows installer behavior on the runner

**Status:** **Blocked — until Phase 5 produces an installer.** Proposed work with nothing to do
until then; the installer it would verify does not exist yet
**Owner:** Implementer
**Priority:** Medium now, High once Phase 5 starts — it must land before the first public release
**Phase:** Phase 5
**Depends on:** the Phase 5 installer, `T-026` (establishes the real-plugin Windows job)
**Relevant context:** `OPS-004`, `REL-001`, `docs/project/TESTING.md` §9, `REQUIREMENTS.md` §3
**Affected surfaces:** `.github/workflows/ci.yml`, `docs/project/TESTING.md` §9, `REQUIREMENTS.md` §3
**Risk:** Medium — same failure mode as `T-026`: a shallow check would retire a
release-blocking manual item without replacing it

#### Scope

Split out of `T-026` when `OPS-004` was accepted on 2026-07-26. `OPS-004` reclassified four
things as automatable on the Windows runner; three of them `T-026` does now, but installer
verification cannot be written before an installer exists, and `T-026` had to stay completable
because it is what closes Phase 0's last exit criterion.

A CI runner is a genuinely clean machine, which is what makes this worth automating at all:
installing onto a box that has never held the application is exactly the case a developer
machine cannot reproduce.

Assert, on `windows-latest`:

1. **Silent install** completes with a success exit code and no interactive prompt.
2. **File and shortcut placement** — the installed tree, the Start Menu entry, and any
   registered association land where the installer claims.
3. **The installed application launches** under the real `windows` platform plugin, reusing
   `T-026`'s harness rather than a second one.
4. **Uninstall and removal** — the uninstaller exits clean and leaves nothing behind except
   what is deliberately preserved (user settings and the job database, per `DAT-001`).

#### Acceptance criteria

- Each of the four is a **gate**, stated as a mutation that turns the suite red: a missing
  shortcut, a file placed outside the install root, a non-zero silent-install exit code, and a
  leftover file after uninstall each fail the job. Screenshots, if any, stay retained evidence
  and fail nothing on their own (`T031-R2`, `P0-R7`)
- Uninstall leaving user data behind is asserted as **intended** behavior, not tolerated as a
  leftover — the test distinguishes the two
- `docs/project/TESTING.md` §9's manual list drops installer placement and removal, and
  `REQUIREMENTS.md` §3 narrows to match — **only once this job is landed and green**
- The added CI time is recorded against `T-006`'s budget

#### Out of scope

- Whether the installer *feels* normal — `OPS-004`'s subjective residue, still human, still
  blocks first release
- Upgrade-over-existing-install and downgrade paths — real, but a separate task once the
  versioning story exists
- Any non-Windows packaging

---

### T-297 — A thumbnail flickers while the window is resized with a panel open, and the cause is unknown

**Status:** **Blocked on `T297-R1` and `T297-R2`, both High — the product fix is sound and the
*record* of how it was reached is not** (reviewed at `d44700c`). Corrections landed 2026-09-03; two
of the three findings need the maintainer rather than more work.

- **`T297-R1` — no real-display capture.** The reproduction was taken on a nested
  `kwin_wayland --virtual`, and its PNG is a labelled reconstruction rather than a captured frame.
  The criterion asks for a real display and a capture. **Needs either a pre-fix run on the live
  session or an explicit amendment** naming what is surrendered. Not mine to take, and not something
  to run unattended on the maintainer's desktop.
#### Ruled 2026-09-04: the exception is granted, and the capture is being taken

**`T297-R2` — exception granted.** The maintainer accepted that criterion 2 was missed and that the
sequence cannot be created retroactively. What stands in its place is the dated correction in
`docs/project/evidence/2026-09-01-T297-panel-collapses-during-resize.md`, which says the cause section is
superseded, names the real writer, and records that the `T-296` relation was backwards. **The
commits are not rewritten.** This finding no longer blocks Complete.

**`T297-R1` — being answered rather than amended.** The maintainer chose to run the pre-fix tree on
a real display and keep an actual capture, over amending the criterion.
`tools/t297_prefix_capture.sh` puts that tree on the display from a `git worktree` at `331845d`,
with `PYTHONPATH` overridden so the editable install cannot serve the fixed code instead. **Until
that capture exists this task stays Blocked**, and a run that does *not* reproduce is a result to
record rather than a reason to try again.

- **`T297-R2` — the pre-fix record names the wrong cause.** `331845d` says the cause is
  `_on_list_resized`'s deferred relayout and that it is *not* `T-296`'s; both are wrong, and the
  real cause first appears in the commit that changes source. **The evidence file now carries a
  dated correction** saying so and recording that the criterion was missed. Moving this to Complete
  needs the maintainer's explicit exception; the commits are not rewritten.
- **`T297-R3` — corrected.** The probe froze only part of itself before the reconstruction, so the
  post-fix counts included the instrument's own forced 26 px. Every counter is frozen now and a
  control asserts none moved — **it caught a real drift on the first run** (38 → 40 paints) rather
  than passing. Both trees were re-measured rather than corrected by subtraction.

**The fix itself was not in doubt in the review and is unchanged.** **It was not the deferral the
entry hypothesised.** `QAbstractItemView` keeps `setIndexWidget` widgets in **the same map as item
editors**, so every `updateGeometries()` pass handed the open row's panel to
`RowDelegate.updateEditorGeometry` — which applied `_control_of`, the row's *format-combo* slot, to
it. A 354 px panel became **26 px**. A resize calls `updateGeometries()` once per step, so the panel
collapsed and was restored once per step, and the view painted the row inside each gap: `paint`
draws the thumbnail on every row it is given, because an open one is supposed to be covered.

**Measured under a compositor before anything was changed**, which is this task's first criterion —
`docs/project/evidence/2026-09-01-T297-panel-collapses-during-resize.md`, with a capture. 110 resize steps:
**107 collapses to 26 px, 107 paints of the row its panel did not cover**, and 109 of 110 steps
nevertheless *settling* correctly, which is why the first reading — which sampled after each step —
saw nothing. After the fix, re-measured 2026-09-03 with the corrected probe: **0 exposed paints, 110/110
settled**, and the panel's own resize events fell from **214 to 8, with 0 collapses to 26 px**. *(This
read "214 to 9" and one collapse; that ninth event and that collapse were the instrument's own
reconstruction — `T297-R3`. The pre-fix figures re-measured identically: 107 exposed, 214 resizes,
107 collapses, 109 of 110 settling.)*

**The fix is the guard its two siblings already have.** `setEditorData` and `setModelData` both
begin `if not isinstance(editor, QComboBox)`; `updateEditorGeometry` did not. Anything that is not
this delegate's editor now goes to `super()`, which sizes an editor to `option.rect` — exactly right
for an index widget spanning the row.

**This is what `T-296` was working around, and that is worth stating rather than leaving to be
rediscovered.** `T-296` reordered `_mount_panel` so `scrollTo` — which calls `updateGeometries()` —
could not undo the geometry `setGeometry` had just set. The reorder is still correct and still
tested; the reason a scroll destroyed the geometry was this method, one layer down. **`T-296` is not
reopened**: it is Complete, approved, and its own regression still passes.

*(Filed 2026-08-28 by `T-212`'s checklist run, deliberately without a cause.* The maintainer's
report: *"when changing the window size while the naming information is up, the thumbnail cuts in
and out very rapidly. That shouldn't happen."*)
**Owner:** Implementer
**Priority:** Low — it is visual noise during a drag, and it is the least understood thing the run
found
**Phase:** Phase 4 (polish; **not** a plan deliverable)
**Depends on:** nothing
**Relevant context:** `ui/add_dialog.py` `panel_height_for`, which reads the **viewport's** height,
so every resize step changes the row's size hint; `_mount_panel`'s note that `setIndexWidget`
defers geometry to `updateEditorGeometries`, which runs on paint; `T-296`
**Affected surfaces:** `ui/row_delegate.py` (`updateEditorGeometry`), `tests/ui/test_row_delegate.py`;
the instrument is `tests/ui/_t297_resize_probe.py` and `tools/t297_resize_session.sh`
**Risk:** Low

#### What was measured, and what it does not show

**It did not reproduce offscreen.** Across eight resize steps with the template panel open:

```
thumbnail loads : 0        # nothing re-fetches
cancels         : 0
```

and the panel's geometry matched the row's `visualRect` at **every** step, from 762 px down to
430 px and back up. So it is neither the thumbnail being reloaded nor the panel losing coverage in
any way a headless process can see.

**The plausible mechanism is unproven and is recorded as a hypothesis, not a finding.**
`panel_height_for` reads `self._list.viewport().height()`, so every resize step changes the row's
size hint; the panel's re-placement is deferred to paint; and the delegate underneath — which draws
the thumbnail — is what shows in any gap. That is consistent with `T-108`'s comments and with
`T-296`, and it is not evidence.

#### Acceptance criteria

- **It is reproduced on a real display first**, with a capture, and the reproduction is recorded in
  `docs/project/evidence/` before anything is changed. An offscreen process does not do a continuous resize
  and its style is not necessarily the session's
- **The cause is named before the fix**, and if the cause turns out to be `T-296`'s, this task is
  closed against that one rather than fixed twice
- **If it proves to be Qt or compositor behaviour** this application can only work around, that is
  recorded as the finding and the workaround is a separate decision

#### Out of scope

- Guessing. `T-296` is filed with a measured cause; this one is not, and the two should not be
  merged on the strength of sitting near each other


---
