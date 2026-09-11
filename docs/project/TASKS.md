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

### T-290 — Offer the yt-dlp update as recovery, not as a setting

**Status:** In Review — **built 2026-09-11**. *(Filed 2026-08-27 to build `OPS-002`'s amendment
of the same day, which
the maintainer ruled during `T-212`'s run: the override stays, and stops being a standing
choice.)*
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

#### 2026-09-10 — what was found already true, and what is left

**Three of the six criteria were already met before this task started**, by `ui/error_text.py`,
which predates it. Measured across the whole taxonomy rather than read:

| Criterion | State |
|---|---|
| A route from a failed download to the update | **Met.** `EXTRACTOR_ERROR`'s next step reads *"The site may have changed. Updating yt-dlp in Settings often fixes this."* (`C-002`) |
| The route is not an advice column | **Met.** One next step per kind, and `GEO_RESTRICTED`/`DRM_PROTECTED` still get **none** — the refusal `T-201` calls the substance of its own task |
| The offer appears only where it could be true | **Met.** Of twelve kinds, exactly one offers it. `DISK` says *"check there is free space"* and nothing about yt-dlp |
| `NFR-007` untouched | **Met.** Nothing here makes the update automatic, silent or implicit |

**A guard was added for the third**, because nothing pinned it: the table had the right shape and
no test stopping a later kind from picking the sentence up by copying a neighbour.
`test_only_a_failure_the_update_could_fix_offers_the_update` asserts it as a property over the
whole taxonomy, both ways — the kind that must offer it and every kind that must not — since half
of it would pass on a table that offered the update everywhere or nowhere. It fails when `DISK` is
given the sentence.

#### What is left, and it is the maintainer's to rule

**Only the Settings presentation**, which this task's first criterion explicitly reserves: *"what it
becomes — reworded, de-emphasised, moved behind a disclosure, or left in place with different words
— is the implementer's proposal and the maintainer's ruling."*

**Deliberately not guessed at overnight.** The four options change what the screen means, not just
how it reads, and building one of them would spend the ruling rather than inform it. `OPS-002`'s
constraints bound whichever is chosen: the resolved version stays visible and revert stays one
action, so *"it must not disappear"* is already settled — what is open is only its weight.

#### Built 2026-09-11 — demoted, and told when

**Ruled by the maintainer from three options**: *demote it and say when*, over rewording alone and
over a disclosure.

**Why not the other two.** Rewording leaves two ordinary buttons side by side, and the complaint is
about **weight** — two equal buttons stay two equal buttons whatever they say. A disclosure was
argued against and rejected for a reason this task created itself: `error_text`'s `EXTRACTOR_ERROR`
tells a user *"Updating yt-dlp in Settings often fixes this"*, so hiding the control makes that
advice dead-end at a closed twisty.

**What changed.** A line above the controls names the occasion — *"If a site has stopped working, a
newer yt-dlp often fixes it. Otherwise the bundled version is the one this application was tested
with."* — and the control reads `Get a newer yt-dlp` at `quietAction` weight, which `theme.py`
draws without a fill and in muted text.

**The fill is what it gives up, and only the fill.** An ordinary button is a `surface` chip on a
`window` ground, so this leaves an outline button beside a filled one — visible in both palettes.

**The border stays, and that is `T-132`.** Making a button transparent *and* borderless turned two
toolbar controls into text nobody could tell was pressable, which the maintainer reported at the
time. The border is what says *pressable*.

**The text colour stays, and a guard is why.** The first version muted it, and
`test_muted_is_either_secondary_emphasis_or_a_published_disabled_state` refused: every other
`muted` rule in this application is either a `:disabled` state or something non-interactive — a
group title, a header strip. **A pressable control in the disabled colour looks unavailable while
responding**, which is a worse defect than the weight being reduced. Registering the selector as
secondary emphasis would have silenced the guard and shipped that; the demotion moved to the fill
instead.

**`OPS-002` is untouched**: the resolved version is still visible, revert is still one action and
is deliberately **not** demoted — a test asserts that, because demoting both would be no
de-emphasis at all. `NFR-007` is untouched: still explicit, never automatic, never silent.

**The two surfaces agree by construction.** The note and the failure's next step describe the same
move, which is `T-243`'s one-voice rule applied across screens rather than within a row.

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

### T-286 — The container section says what recode costs and never what it is for

**Status:** In Review — **built 2026-09-10**. *(Filed 2026-08-27 during `T-212`'s run, from the maintainer's question:
*"Does re-encoding provide any tangible benefits over remuxing the files? Seems like the option is
pointless."* **It is not pointless, and the fact that the dialog left that question open is the
defect** — the note beside the radios states the cost of recoding and never the case that buys it.
**The option stays**; this task changes what the dialog says about it.)*
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

#### Built 2026-09-10

The note now reads:

> Remuxing keeps the streams and is quick; recoding re-encodes them and is not. Recode only when a
> player refuses what the site sent — a new wrapper does not change what is inside it.

**The second sentence carries the case and the trap in one breath**, which is what the measurement
made possible: remuxing a `vp9 + opus` webm to mp4 *succeeds and leaves `vp9 opus` inside*. So the
useful thing to say is not *"recode is slower"* — the reader already had that — but *"a new wrapper
does not change what is inside it"*, which is what makes the first half actionable.

**Bounded by *only when*, deliberately.** Format selection answers the ordinary case with no
conversion at all, so a sentence that read as advice to recode would trade one wrong default for
another.

**Moved to a named constant** so the wording is asserted the way this dialog's other fixed strings
are, and cannot drift back to cost-only. The regression checks the four criteria **separately** —
cost stated, case named, not advice, and why remux does not cover it — plus that no codec name
leaks into a register the rest of the dialog does not use. A single "did the wording change" check
would have passed on any edit.

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

### T-316 — A staged row that failed looks like one that worked

**Status:** In Review — **built 2026-09-10**, the same day it was filed from the built window, during `T-297`'s session:
*"even a failure to grab shows up as green here (should probably show as red?)"*
**Owner:** Implementer
**Priority:** Low — nothing is wrong in words, and the row does say what happened. What it costs is
a glance: a paste of twenty has to be read line by line to find the one that failed
**Phase:** Phase 4 (polish; **not** a plan deliverable, and **not** Phase 4 exit work). Filed after
the maintainer ruled to ship; the placement is theirs and `T-286`/`T-290` are ahead of it
**Depends on:** nothing
**Relevant context:** `ui/add_dialog.py` `StagingModel.data`, which answers `STATE_ROLE` and not
`STATE_CHIP_ROLE`; `ui/row_delegate.py:1902`–`:1916`, the chip; `ui/theme.py:993`, the selected-row
rule; `T-130` (selection is geometry, not tint); `NFR-005`; `UX-005` §3
**Affected surfaces:** `ui/add_dialog.py`, possibly `ui/row_delegate.py`, and their tests
**Risk:** Low — additive, and the one thing it must not do is make state a colour-only signal

#### What was seen, and what it actually is

A staged row whose probe failed reads `extractor_error: … — Couldn't read`, and the only coloured
thing on it is a **2px brand-green bar down its left edge**. The report was that green reads as
success.

**That bar is the selection indicator, not a state.** `ui/theme.py:993` draws
`QListView::item:selected { border-left: 2px solid primary }`, and `T-130` chose geometry
deliberately so that selection is a *shape* rather than a tint. It is green on every selected row,
whatever the row is doing. So the fix is **not** to recolour it: making the selection bar carry
state would give one signal two jobs, which is what `T-130` separated.

**The real asymmetry is that a staged row has no state marker at all.** `QueueModel` answers
`STATE_CHIP_ROLE` and the delegate draws a bordered chip on the row's title line; `StagingModel`
answers that role **nowhere**, so a staged row's state lives only as a clause inside the detail
text. Verified on current code, not on the 2026-09-01 screenshot the report came from.

**No surface colour-codes state today, and that is on purpose.** The queue's chip is drawn in the
`muted` pen — it is a shape with a border, not a colour. `NFR-005` bans conveying information by
colour *alone*; it does not ban colour as a second channel beside a shape and a word. So a failure
tint is available, and is the kind of thing to propose rather than assume.

#### What this task does not decide

**Whether the answer is a chip, a tint, an icon, or the row's existing words in a different place.**
The report asked for red; the narrowest fix that matches the queue is a chip, which needs no new
colour vocabulary at all. A maintainer ruling picks between them, from mockups, the way `T-310`'s
and `T-313`'s were taken.

#### Built 2026-09-10 — the chip, and why not red

**A staged row now answers `STATE_CHIP_ROLE`**, which is the role the queue already answers and the
delegate already paints. Nothing new was drawn and no colour was invented.

**The report asked for red and this does not give it**, which is a proposal rather than a
dismissal. Three reasons, in order of weight:

1. **This theme has no failure hue.** Adding one is contrast work in both palettes (`T130-R1`) and
   a vocabulary every other surface would then have to honour — for a signal a shape already
   carries.
2. **The queue solved the identical problem with a chip** and its reasoning transfers verbatim: *a
   queue is a list of rows in different states and the state is what the eye is hunting for.* A
   staging list is the same shape of thing, so a second vocabulary would be the drift `T-186`
   records.
3. **`NFR-005` permits colour as a second channel**, so red is still available later. It is
   additive to this, not blocked by it — which is why the narrow fix went first.

**The bare state, not `state_text`.** `T130-R3` drops the state from the detail line only where the
chip repeats it exactly, so an ordinary row says it once and a duplicate still says both halves.

**Ruled 2026-09-11: ship the chip, decide on the tint after seeing it.** The maintainer took the
narrow fix and kept the colour question open rather than closing it either way — `NFR-005` leaves
colour available as a second channel, so adding the tint later costs nothing that doing it now
would have saved, and the chip may already do the job. **The chip is what a tint would be added
to**, not an alternative to it.

#### Acceptance criteria

- **A failed staged row is distinguishable from a settled one at a glance**, without reading its
  detail line.
- **The selection bar is unchanged.** Selection stays one signal meaning one thing (`T-130`).
- **State is not conveyed by colour alone** (`NFR-005`), whatever channel is chosen.
- **The staging list and the queue agree** about how a row states what it is, or the difference is
  recorded as deliberate.
- Asserted by a test that fails against the present rendering.

#### Out of scope

- The queue's own rendering. It already marks state; this is about the list that does not.
- Recolouring the selection indicator, for the reason above.

### T-297 — A thumbnail flickers while the window is resized with a panel open, and the cause is unknown

**Status:** **In Review — both maintainer-held findings are dispositioned as of 2026-09-10.**
`T297-R2` was granted an exception on 2026-09-04; `T297-R1` was answered on 2026-09-10 by a
maintainer observation on a real display **in place of a capture**, which amends criterion 1 rather
than satisfying it — see below. *(Was: Blocked on `T297-R1` and `T297-R2`, both High — the product
fix is sound and the* record *of how it was reached is not, reviewed at `d44700c`.)*

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

#### 2026-09-10 — `T297-R1` answered by observation, not by capture

The maintainer chose to watch rather than record: *"lets run it and have me watch."* The pre-fix
tree was put on their own Wayland session from the `331845d` worktree, and afterwards they reported
**no flicker** — *"there is no flicker at all anymore with the thumbnails or the screen … its all
good."*

**What this is worth, stated rather than glossed.**

- **It amends criterion 1; it does not pass it.** That criterion asks for a *capture*. None exists
  and none will. What stands in its place is the maintainer's own eyes on their own display —
  better than the nested `kwin_wayland --virtual` the reviewer rejected, weaker than the frame the
  criterion names.
- **Which build was observed could not be established from this side.** Two windows were open at
  the time — the pre-fix worktree and the maintainer's own current build — and the implementer
  verified only that both existed, not which was dragged. The two mean opposite things: on current
  code `T-312` has removed row-mounted panels entirely, so **no flicker is the only possible result
  there**, and it says nothing about the defect.
- **So this record claims the weaker reading**: the maintainer is satisfied the built application
  does not flicker. Whether the pre-fix tree still reproduces on real hardware is **not** answered
  here, and nothing below should be read as saying it is.

**Why that is acceptable rather than a gap to chase.** The cause is known and measured — 107
collapses to 26 px across 110 resize steps, `updateEditorGeometry` applied to a panel it should
never have been handed — and the fix is the guard its two sibling methods already had. `T-312` has
since removed the mechanism outright. What a capture would have ruled out is that the nested
compositor *exaggerated* the originally reported symptom; that question is now unanswerable by any
means, because the surface it lived on no longer exists.

**A tool defect was found and fixed while doing this.** `tools/t297_prefix_capture.sh` told the
reader to paste `https://archive.org/details/TheArtOfWarBySunTzu`, which no longer resolves —
*"opening play-av tag not found"*. The local fixture of that name still works; the live URL behind
it does not. The guide now asks for any URL the reader knows resolves, since nothing in that step
is site-specific.

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

### T-315 — A queue row's `⋮` offers what the row already shows

**Status:** In Review — **built 2026-09-10**; both design questions ruled by the maintainer the
same day from the built queue window.

**Owner:** Implementer
**Priority:** Medium — the control works since `T-314` and now opens a menu whose every entry
repeats a button beside it, which is `UX-005` §5's defect one step on from the one just fixed
**Phase:** Phase 4 (accessibility and polish)
**Depends on:** `T-314` connected the zone at all. `T-311` is where the composition rule comes
from and `T-135` is where this redundancy was fixed on the other control.
**Relevant context:** `UX-011` option *E* (the staging list's row menu); `T-135` (the `⋯` overflow
holds only what did not fit); `UX-003` (a job enters the queue once it has been read); `T-311`
(streams and preset are different facts); `UX-005` §5
**Affected surfaces:** `ui/queue_view.py`'s row wiring; `ui/main_window.py`'s row menu; new
`ui/format_dialog.py`; `core/presets.py`
**Risk:** Medium — a new asynchronous surface with three ways to end without a table, and two
editors that write a whole request back

#### What was reported, and what it turned out to be

*"The options from that button seem completely redundant. I think it should give you options/choose
formats like it does when you do it on the add urls."*

`T-314` wired the `⋮` to `_row_menu_asked_for`, which carries `verbs_of` — **everything the row's
state permits**, which on any window wide enough is exactly the four buttons already drawn on the
row. `main_window.py` records `T-135` fixing this same redundancy on the `⋯`, and the fix
reproduced it one control over. The zone now has its own signal: `⋯` holds what the row could not
draw, the keyboard routes hold every verb, and `⋮` holds what can be done to **this download**.

#### The two things that had to be ruled

1. **A queued job does not carry its formats.** `Job` holds the request, title, uploader, duration
   and thumbnail; the probe's list lives in the add dialog's `MediaInfo` and is discarded when that
   dialog closes, and no migration ever persisted it. **Ruled: re-read the URL when the entry is
   picked.** The alternative — storing the list — opens the table instantly at the cost of a
   migration, a blob per job, and a list that can go stale; a stale list fails *at download time*,
   silently, long after the choice was made. A re-read costs a second and is true at the moment it
   is chosen from.
2. **Whether the menu also lists the row's verbs**, as the staging list's menu does under its
   *"Just this item"* section. **Ruled: per-item commands only** — the verbs are already buttons,
   and `⋯` exists for whichever of them a narrow window could not draw.

#### What that needed underneath

**`presets.preset_of` — the inverse `to_request` never had.** Both entries write a whole request
back, and both must open on **the preset the job's request implies** rather than on a catalogue
preset matched by name: a queued request is whatever the add dialog composed for it, and a preset
agreeing on the format need not agree on the thumbnail, the subtitles or the naming. Opening on
the wrong one would show settings the job does not have and write them back on OK — `T-313`'s
silent discard from a new direction. Built by name from `PRESET_OWNED_FIELDS`, exactly as
`format_choice_of` narrows the other way, so the two directions cannot disagree.

**It is not an identity in both directions, and the test says which one holds.** A preset stating
an empty `output_template` means *"whatever the caller's default is"*, so `to_request` resolves it
and the request records the concrete string — information the preset never held. Every shipped
preset states none, so `preset_of(to_request(p))` differs from `p` in exactly that field.
**Request → preset → request is lossless**, which is the direction a retarget travels, and that is
what is asserted. The first version of the test asserted the other direction and failed.

**One retarget route, three callers.** The preset control, *Options…* and *Choose specific
formats…* all end in `_retarget_to`, so `T197-R4`'s carried-over connection and `T-195`'s
carried-over naming cannot be remembered on one path and forgotten on another.

#### Corrected 2026-09-10 after review — `T315-R1` to `T315-R4`

**`T315-R1` — the item commands were reachable by pointer only.** The `⋮` is a painted affordance
with no accessibility node, and that is allowed *because the same menu is reachable by right-click,
the Menu key and Shift+F10* — a justification this task made untrue by giving the zone its own
signal and leaving the keyboard route on `verbs_of` alone. The reviewer measured it: a
keyboard-reason context event opened `↑ ↓ Cancel Remove` and neither new command (`NFR-005`).

**One builder, two menus, differing only in the company the commands keep.** `_add_item_commands`
fills both; the `⋮` opens the commands alone, as ruled, because a pointer user can see the verbs
as buttons, and the keyboard route opens them **above** the verbs, as the staging list does.

**`T315-R2` — a playlist header offered a `⋮` that opened nothing.** The header paints a preset
control (`UX-005` row 13 defines retargeting across members), so the zone was drawn beside it — but
its `JOB_ID_ROLE` is the *playlist* id, which `job_for` cannot resolve. The offer is withdrawn
rather than implemented, and the reason is the commands themselves: **a format id names one
video's stream**, so applying one member's choice to the others would be wrong rather than merely
unbuilt (`T-110`'s rule, which the staging list already follows by omitting the entry there).

`MENU_AVAILABLE_ROLE` is how a model says a row has an item menu; `_menu_zone_of` answers an
**empty rectangle** when it does not, which is what makes the paint, the hover and both hit-tests
follow from one definition instead of four that could disagree.

**`T315-R3` — the Options editor was lossy for audio qualities it does not itself offer**, so this
task's promise of lossless editing was not kept and the download's encoding could change silently.
Two causes: `_show_preset` fell back to index `0` when `findData` missed, showing `320 kbps` for a
request asking for `96`; and `_chosen_audio` cleared any non-MP3 quality even when the codec had
not changed. The reviewer's matrix — MP3 at `0`, at `96`, at nothing, and AAC at `3` — is now a
parametrised regression with the passing `192` case kept as its control.

**The fix is `T-313`'s own rule, one dialog over:** a group nobody touched decides nothing, so the
request keeps what it arrived with; a codec the user actually changed still clears a bitrate that
belonged to the old one (`T076-R1`). The bitrate control also shows the value the download carries,
inserting an entry only when it describes the current state — `RowDelegate`'s rule for a row's own
non-catalogue preset. **The defect predates this task and reaches the staging list's editor by the
same code**, which is why both the fix and its tests sit on the dialog.

**Auditing the staging caller, as the finding asked, turned up a distinction worth recording.** Only
half the matrix can reach that surface: `preset_for` runs every MP3 preset through `effective`,
which replaces its bitrate with the one the dialog's own control shows (`T118-R6`), so an unlisted
MP3 quality is normalised before the editor is built. A first version of that test used MP3 at `0`,
got `192` back, and was measuring that derivation rather than the defect. `effective` returns a
non-MP3 preset untouched, so the **codec** half is reachable there and is what the staging
regression uses.

**`T315-R4` — the probe tests called their slots directly** while describing themselves as
delivering the manager's signal, and neither the *no formats* nor the *started meanwhile* ending
had a test at all. All four now emit on `media_probed` / `job_failed`, so the connection is part of
the claim, and both endings are covered — the race by mutating the queue the window reads and
calling the refresh the window itself calls, rather than by arranging the model directly.

#### Corrected again 2026-09-10 — `T315-R5`, a regression the first correction introduced

**Authorised by the maintainer** under `TESTING.md` §14, whose two-pass budget was spent and whose
remaining blocker was Medium: *another focused pass*, taken because `T313-R3` is High and forces a
further round over the same correction boundary regardless, so the marginal cost was the fix rather
than a review cycle.

**`_row_menu` serves both routes, and `T315-R1`'s shared builder did not know which had asked.**
Adding this download's own commands for the keyboard put `Just this item`, `Choose specific
formats…` and `Options…` into the pointer's `⋯` as well — the one menu whose entire purpose is
*the verbs the row had no room to draw* (`T-135`). Three entries that always fit elsewhere, above
the two that did not.

**The view says which route asked**, because the shell cannot recover it: sending the verbs alone
distinguished the two while both menus held only verbs, and stopped being enough the moment one of
them held something else. `more_requested` carries that now, and the item section is built only for
the context and keyboard routes.

**The spillover was invisible to every committed test**, because none of them took the pointer
route — `_on_verb` and `_show_row_menu` were called directly. The new regression clicks the drawn
`⋯` itself, and the keyboard route is asserted separately so the two cannot be satisfied by one
change.

#### Acceptance criteria

- The `⋮` offers *Choose specific formats…* and *Options…*, and **none of the row's verbs**.
- A job that can no longer be retargeted is offered no menu at all.
- Picking formats re-reads the URL, opens the table on what it found, and composes the chosen
  streams over the request the job already has — options, subtitles and naming all survive.
- Accepting *Options…* without changing anything changes nothing.
- A read that fails, finds no formats, or finishes after the job started says so in the status bar
  and writes nothing.
- A probe this window did not start is ignored, since both signals are shared with the add dialog.
- Each is asserted by a test that **fails against the behaviour it replaces**.

### T-313 — The preset control discards a hand-picked format, and Notes repeats the row

**Status:** In Review — **built 2026-09-10**, both halves ruled by the maintainer the same day
from the built window while `T-312` was in review.

**Owner:** Implementer
**Priority:** High — the first half is silent data loss on the screen a user reaches immediately
after choosing formats, and it fires without any gesture at all
**Phase:** Phase 4 (accessibility and polish)
**Depends on:** nothing. `T-311` is where the first half came from and `T-310` the second.
**Relevant context:** `UX-004` (a row inherits the batch preset unless it has its own); `T-311`'s
ruled fourth sequence; `REQ-003` (the table shows notes); `T310-R1` (removing the field is a High
finding); `T126-R3` (the queue's value guard)
**Affected surfaces:** `ui/add_dialog.py`'s *Download as* control; `ui/format_table.py`'s two lists
**Risk:** Low — both are narrowings of behaviour that already existed, and the route back from a
hand-picked format is the part that had to be held in place rather than changed

#### 1 · A chosen format is discarded without being asked to be

*"The format reverted back to 'best video available' despite me not actually selecting it in the
dropdown."*

**Two causes, and the second was not reported.**

**(a) Qt commits an open editor on every refresh**, and for a row that *inherits* the batch preset
the committed value is the inherited entry's `None` — which the guard could not tell apart from a
user choosing *follow the batch*. Opening the control and clicking elsewhere silently discarded a
hand-picked format. **`T-311` opened this by design**: it stopped writing the pick into
`row.preset` so the batch control could keep reaching a row that had picked streams, and the cost
was that an inheriting row *with* a pick answers `PRESET_ROLE` exactly as an untouched one does.

The fix is `T126-R3`'s, brought one dialog over — **the guard is on the value, not on the caller**,
comparing against `PRESET_ROLE` itself so the two cannot drift. It subsumes `T-108`'s narrower
case, which is the same shape one state over.

**(b) Naming a preset also discarded the pick**, which contradicts the fourth sequence the
maintainer ruled on 2026-09-10: *"changing Preset now reaches the row and keeps your streams."*
The clearing line predates `T-311` and was correct when written — the format panel then wrote its
selector into `row.preset`, so naming a preset really did replace what the row would download —
and it was never reconciled with the ruling. **Found while tracing (a), reported rather than
changed, and ruled by the maintainer:** *"yes, match the ruling."*

Only *follow the batch* clears now, which is `T-311`'s own answer to *"how is a stream choice
cleared?"* — and that route is reachable from every state precisely because naming a preset no
longer consumes it. `test_following_the_batch_still_gives_up_a_chosen_format` holds it there;
`T-310`'s review already caught one false claim in this repository that no route back existed.

#### 2 · A note that only repeats the row

*"For video, it just repeats the resolution, and for audio I'm not even sure what it's trying to
say. Seems like a redundant or useless field right now."*

**Measured on the maintainer's own probe:** the video notes read `1080p`, `720p`, `480p` beside a
**Quality** column saying `1080p`, `720p`, `480p`; the audio notes read `medium`, `medium`, `low`,
`low`, `low` beside bitrates that already ordered them exactly.

**The column is suppressed, not removed** — ruled from three options, *"show it only when it says
something."* `REQ-003` names notes and `T310-R1` called their removal a High finding, and it was
right for a reason that survives: on archive.org the note is the only thing distinguishing two
rows of identical quality, codec and container, one marked `original` and the next `derivative`.

So a note is dropped when every word of it is already on the row — an exact match against yt-dlp's
ordinal audio words, against the two phrases that restate which list the row is in, or against the
Quality cell itself — and the **column** goes when no format in that list has anything left. On
YouTube it disappears and gives its width back to the columns being read; on archive.org it
appears. Matching is exact, never by substring, so `medium, original` keeps both halves.

#### Corrected 2026-09-10 after review — `T313-R1`, `T313-R2`

**`T313-R1` — the clear-route was inert from the one state it was promised for.** The guard returns
early when the committed value equals `PRESET_ROLE`, and a row that **inherits** the batch preset
while holding a pick answered `None` there — exactly as an untouched row does. So *follow the
batch*, this task's own answer to *"how is a stream choice cleared?"*, changed nothing from that
state. The committed clear-route test assigned an owned preset first and so never entered it.

**Fixed by making the two states differ in value, not by a second guard about how `setData` was
reached.** `PRESET_ROLE` now answers what the row will actually download — the composed name — so
an untouched commit re-states `137+140` and clears nothing, while the inherited entry is a
different value and clears the pick. It also makes the control agree with the row, which already
painted *"Download as: 137+140 — following the batch"*, and revives `RowDelegate.createEditor`'s
branch for a row's own non-catalogue preset that `T-311` had left unreachable.

**`T313-R2` — suppressing a tier note is only honest where the row states the tier.** Every ordinal
word went regardless of whether the row had a bitrate to repeat, and the reviewer found the cost:
two audio-only Opus formats with unknown bitrate *and* size, noted `low` and `high`, lost both
notes and the column, and nothing else on either row told them apart. **Exact string matching never
established redundancy** — the neighbouring cell does. A tier note now goes only where a bitrate is
shown, and a *video only* / *audio only* note only where the row's own flags already establish it,
which leaves it standing on a stream yt-dlp never classified.

#### Corrected again 2026-09-10 — `T313-R3`, a regression the first correction introduced

**The fix for `T313-R1` created an automatic-commit discard of its own**, which is the same defect
class one transition over and is recorded here rather than smoothed away. `PRESET_ROLE` began
answering `format_name` of the **composed** preset — a value that grows a clause for every field
the governing preset sets, so changing the batch to one embedding metadata turned `137+140` into
`137+140 · embedding metadata` **while the editor was open**. `setEditorData` searched only the
entries already built, `findData` missed, the combo fell to index `-1`, and its next untouched
commit arrived as `None`: the user deliberately choosing *follow the batch*. Reproduced by the
reviewer through a wheel event on the batch control, with nothing else touched.

**Two corrections, and the second is the one that generalises.**

1. **The role answers the selector**, not the composed name. The selector changes only when
   different streams are picked, which is the one event that *should* invalidate the entry. What
   the row downloads in full is on its detail line, where a growing description costs nothing.
2. **A value the editor has no entry for now gets one**, in `setEditorData`. On this list `-1` is
   not neutral — its `currentData()` is `None`, which *is* the inherited entry — so a miss reads as
   a deliberate choice. The guard is the presence of an inherited entry rather than the surface's
   name: the queue has none, so `-1` stays the honest rendering of *"no built-in describes this"*
   there (`T126-R2`), and that is asserted alongside.

**A docstring claimed this could not happen.** `setEditorData` said *"a miss on the staging list
cannot happen — its `None` is the inherited entry, which is present there."* The sentence had it
backwards: the inherited entry being present is precisely what makes a miss dangerous. It is
corrected in place rather than deleted.

#### Acceptance criteria

- Committing the preset control without choosing anything changes nothing, for a row that inherits
  the batch preset as well as one with its own.
- Naming a preset keeps the streams and applies the preset's other settings over them.
- *Follow the batch* still gives up a hand-picked format, from every state a row can be in.
- A note that repeats the row is not shown, one that adds something is, and the column is present
  exactly when some row in that list has something to show.
- Each is asserted by a test that **fails against the behaviour it replaces**, run and recorded.

## Ready

### T-311 — The batch preset control looks like it governs a row it cannot touch

**Status:** In Progress — **ruled by the maintainer on 2026-09-10 from four rendered sequences**
(`tools/preset_override_mockup.py`): *"go with the fourth one"* — **fix the loss and the control**,
which is option (1) in its `E2` shape and what the reviewer independently recommended.

Reported by the maintainer on 2026-09-09 from the built window, in the same session as `T-310`:
*"there is a preset selection at the bottom of that screen that doesn't do anything."* **What the
mockups then found is worse than the report**: picking a format by hand calls
`presets.custom_preset(selector)`, which builds a `Preset` from nothing — so a row set to *Audio
only (MP3)* with a typed filename pattern loses **both**, silently. The reviewer confirmed it on a
real submitted request. The inert control is the symptom; the discarded preset is the defect.

#### What was ruled, and the three questions it forces

**The row records only which streams were picked**, in `Row.format_selection` — which it already
stores — and `preset_for` applies that over whichever preset governs. Nothing is written to
`row.preset` by the format panel at all.

1. **Does an explicit conversion still apply to hand-picked streams?** **Yes.**
   `ui/format_selection.py` says a chosen stream is downloaded *"as served"*, without adding
   extraction — but that clause is about the app **inferring** a conversion from the fact that the
   chosen format is audio-only, which is why `media_kind` stays `VIDEO` for such a choice. A preset
   the user selected is an instruction rather than an inference, and honouring it is what makes the
   control mean what it says. **This changes documented behaviour and is recorded here as the
   decision it is** — every option except *leave it alone* makes the same change, and the two that
   snapshot make it silently.
2. **How is a stream choice cleared?** Through the row's own preset editor, whose *follow the
   batch* entry already clears `format_selection` (`T310-R4`'s audit put it there). There is a route
   back; `T-310`'s review corrected an earlier claim in this file that there was not.

   > **Corrected 2026-09-10 by `T-313`.** As built, **every** preset change cleared it, not only
   > that entry — so naming a preset silently discarded the streams, which is the opposite of what
   > the ruled fourth sequence showed. Worse, Qt commits an open editor on every refresh, and for
   > an inheriting row that commit *is* the *follow the batch* value: the clear fired with no
   > gesture at all. Both are fixed there; the route named above is the only one that clears.
3. **Do explicit row overrides survive?** **Yes, and this is the part to test rather than assume.**
   A preset written by the row editor or the options dialog is the row's own and the batch must not
   reach it; the stream choice composes over whichever preset applies, not over the batch's alone.
   The reviewer noted the mockup's unconditional switch does not demonstrate this, and it does not.

#### What the row will say

Unchanged: `ui/format_text.format_name` matches a built-in on **every** identifying field, so a
preset carrying a hand-picked selector matches none and falls through to the literal. Measured
before building: a composed preset over *Audio only (MP3)* names itself `137+140`, exactly as the
discarded custom preset did. The shared naming rule absorbs this without being told.
**Owner:** Maintainer to rule; Implementer to build
**Priority:** Medium — it is a control that silently does nothing, which `UX-005` §5 names as a
defect in its own right, and it is on the screen a user reaches while choosing formats
**Phase:** Phase 4 (accessibility and polish)
**Depends on:** nothing. `T-310` is where it was found, not where it lives.
**Relevant context:** `UX-004` (a row inherits the batch preset unless it has its own);
`ui/add_dialog.py` `preset_for`, `_on_preset_changed`, `_show_selector`; `UX-005` §5
**Affected surfaces:** `ui/add_dialog.py`'s *Download as* group
**Risk:** Medium — every option changes what the batch control means, which `UX-004` ruled

#### What happens

The *Download as* combo is the **batch's** control: a row uses it unless the row carries a preset
of its own (`UX-004`). Choosing formats in the panel writes one of its own — `row.preset =
custom_preset(selector)` — and from then on:

- `preset_for(row)` returns the row's, so changing the combo **changes nothing** for that row;
- the combo still displays the batch preset's name, so it reads as a description of what will be
  downloaded when it is not;
- `_show_selector` does tell the truth underneath — *"This row · Format selector: 137+140"* — so
  the screen contradicts itself rather than merely omitting something.

With a single staged row, which is the common case, the combo is inert and looks authoritative.

#### Options

1. **The combo tells the truth about the row in hand.** When the current row carries its own
   choice it shows a `Custom formats` entry, and picking a real preset from it **replaces** that
   choice. The control becomes accurate *and* acquires an effect, and it is the way back from a
   custom selection, which there is currently no control for at all.
   *Cost:* the combo becomes row-aware, which narrows `UX-004`'s batch semantics.

   > **Corrected 2026-09-10 by `T310-R8`.** This option was written up as *"the way back from a
   > custom selection, which there is currently no control for at all"*, and that is false: the
   > row's own preset editor and `StagingModel.setData` already offer both a preset and a return to
   > the batch. What is actually wrong is their **discoverability** and the batch control's
   > misleading presentation, which is a narrower and more honest subject. The claim was made in
   > this file and repeated to the maintainer; it is corrected in both.
2. **Disable it while the current row overrides**, with the reason stated where it sits.
   *Cost:* wrong for a multi-row batch — the combo still governs every other row, so disabling it
   takes away a working control to explain one that is not.
3. **Leave it and strengthen the line beneath** to say the row is using formats the user chose.
   *Cost:* cheapest and least honest — the combo still looks like the answer.
4. **Remove it from the dialog.** Refused: `UX-004` rules the batch control, and most sessions
   never open a format panel at all.

**Recommendation: (1)** — on narrower grounds than it was first written on. The original argument
was that it is *"the only option that leaves the user a way back"*, and the correction above
withdrew that: the row's preset editor and `StagingModel.setData` already offer one. What survives
is that (1) is the only option where the control **means what it appears to mean** — the combo
names what the row will use, and picking a preset does what a person expects. `UX-005` §6's
*Download as* retarget on the queue row is the same gesture one surface over.

**The reviewer recommends option (1) in its `E2` shape** (`docs/project/reviews/T-310.md`,
2026-09-10) — stream choices and processing settings represented independently, explicit row
overrides preserved, and batch changes reaching only the rows the batch governs unless `UX-004`
itself is changed. It also names a policy question this task must answer rather than assume:
`ui/format_selection.py` documents individually chosen streams as downloaded **as served, without
adding audio extraction**, so preserving an MP3 conversion across a format choice is a *new design*
rather than a restored one. The output-template reset has no such justification and is loss either
way.

#### Acceptance criteria

- With a row carrying its own formats, the combo and the selector line **agree**.
- Whatever is ruled, the control either has an effect on the row it appears to describe or says
  why it has none. A third state — displaying a preset the row is not using — is the defect.
- A multi-row batch keeps a working batch control.

### T-301 — Four UI tests break when the application font grows by one point

**Status:** In Progress — **three of the four repaired 2026-09-10**; the fourth is diagnosed and
not fixed, and what was tried is recorded below. *(Found 2026-09-08 while repairing the two that
`ubuntu-latest` broke.)*
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

#### 2026-09-10 — the cluster of three, and what a larger font actually does

**All three were test debt, and the product was never wrong.** Each invented a row —
`QRect(0, 0, 700, 66)`, sometimes with 100 px carved off the left — which is a row *at one font*.
A point larger and nothing fitted inside it, so `_verb_rects` answered empty and the test failed
for having guessed the geometry rather than for anything the delegate did.

**Re-expressed against the seam the paint itself uses:** `visualRect` for the row and `_verb_area`
for the region reserved in it. The claims are unchanged — verbs inside the row, right to left, not
overlapping, off the first two lines — and now hold at both fonts.

**One of the three also had a literal the comment beside it rejected.** It searched for the width
where two rows both overflow *"rather than writing it down, because a literal here would be a
number that passed on this machine"* — and then bounded the search at `range(24, 200, 2)`. The band
moves with the font, a point larger put it past 200, and the search ran off the end. The ceiling is
now the row's own width.

**So: a larger font does nothing to verb placement**, which is this task's fourth criterion
answered. `tests/ui/test_row_verb_wiring.py` passes in full — 62 tests — at both fonts.

#### The fourth is not fixed, and these are the measurements

`test_the_menu_key_reaches_the_current_rows_menu` still fails its second half at one point larger:
*"with no current row and no row under the point, a menu opened anyway."* Established by probe:

- The current index **is** invalid when the event is sent (`row: -1`).
- The probe point **is** off every row, and still is with a twenty-pixel margin.
- Exactly **one** `QMenu` exists; `_close_menu` hides it and `WA_DeleteOnClose` does **not** destroy
  it. The same object becomes visible again when the next context event reaches the viewport.

So the menu is not built a second time — a hidden popup is re-shown. `AddUrlDialog._show_row_menu`
cannot be the route, since with no valid index it returns before building anything.

**Two fixes were tried and both rejected**, recorded so the next reader does not repeat them:

- **Widening the probe point's margin** from 2 px to 20. The original margin was exactly two pixels
  at the larger font, which looked like a coordinate-space bug between `customContextMenuRequested`
  (list coordinates) and `indexAt` (viewport coordinates). **It is not that** — the failure survives
  the wider margin. The margin is kept anyway: a probe whose correctness depends on a frame width
  being zero is measuring the frame.
- **Forcing the menu's destruction** in `_close_menu` with `setParent(None)` plus `deleteLater`.
  This made the test fail at the **default** font too, so it trades a font-specific failure for an
  unconditional one. Reverted.

**Ruled 2026-09-11: leave it failing and documented.** The font lever is deliberately not wired
into CI — this task's own *Out of scope* says why — so nothing is red anywhere, and the diagnosis
plus both rejected fixes are the record a later reader inherits. **An `xfail` scoped to the lever
was offered and declined**: this task's own criteria forbid loosening an assertion to reach green,
and a marker saying a known failure is expected is that with extra steps.

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


## Proposed — Phase 5

*Created 2026-09-10, when Phase 4.5 was resequenced to follow the first release and this
phase became the next one to run. `T-039` also carries `**Phase:** Phase 5` and stays under
`## Blocked`, because that section is about status rather than phase.*

### T-212 — The recorded checklist run: the built window against the agreed flow

Historical evidence relocated 2026-09-08:
[Additional historical evidence](COMPLETED_TASKS.md#t212-validation).

**Carries one row by maintainer direction, 2026-08-13:** the **deferred panel mount**. `T-221` was
closed on a real-display observation — the maintainer did not see the one-turn transient — and the
maintainer directed that it be re-checked by hand in this pass rather than left as an open task.
One observation on one machine is evidence about that machine; this run is where a second is taken
deliberately, in front of the whole built window, and **recorded** in `docs/project/evidence/`. Both panel
kinds, since `T-209`'s audit found both spend that turn at 190×26.

> **Superseded — ruled by the maintainer on 2026-09-10:** *"the direction is overridden by the work
> done for T-312."*
>
> The mechanism it aimed at no longer exists. A panel is a **page of the add dialog** now rather
> than a widget mounted into a list row, so there is no `setIndexWidget` turn at 190×26 for either
> kind and the transient the direction asked to have confirmed cannot occur. **This run no longer
> carries a directed row**, and `T-221` needs no second observation.
>
> Checklist row `5.6` stays, as an ordinary row rather than a directed one: a page swap can still
> land badly, and looking costs nothing. It is no longer evidence anybody is owed.

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
**Priority:** High — it is a release gate. *(Was: "a phase exit criterion, and the phase cannot
exit without the evidence". **Amended 2026-09-10**: the maintainer ran the list informally, ruled
that sufficient for Phase 4 closure, and moved the recorded run to Phase 5 — so it now gates the
first release rather than the phase.)*
**Phase:** **Phase 5** *(moved 2026-09-10 from Phase 4, by maintainer ruling: "I did a mostly
full informal run … please defer that task to the end of phase 4.5 or as part of phase 5"; Phase 5
rather than 4.5 because 4.5 was resequenced the same day to follow the release, and a checklist
run that happens **after** shipping is not a release gate at all)* — **last.** The plan's own criterion text says why: a run taken before the
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

#### Moved to Phase 5 on 2026-09-10, and what that changes

**Ruled by the maintainer** after an informal pass over the built window: *"I did a mostly full
informal run … and I think things are looking good for it. Please defer that task to the end of
phase 4.5 or as part of phase 5."*

**Phase 5, not the end of 4.5**, because 4.5 was resequenced the same day to follow the first
release — a checklist run taken after shipping gates nothing. In Phase 5 it sits beside the Windows
manual verification session, which needs a real desktop too, so the two sittings can be arranged
together.

**What the informal run does not do, said plainly.** This task's own reasoning is that *a
walked-through session is not evidence* — Phase 2's equivalent found **eleven defects against 2153
passing tests** and needed two further runs to reach 40 of 40. The informal pass is what closes
Phase 4; it is not what closes this task. The acceptance criteria below are unchanged, and the run
happens against the built artifact rather than a developer checkout, which is strictly better
evidence than a Phase 4 run would have been.

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
**Phase:** Phase 1 *(**Reassigned to Phase 5 on 2026-09-10 by maintainer ruling**, with the other Windows-only
tasks: *"defer the windows specific screen tasks to the same phase. They should no longer block
phase 4 closure."* It did not block Phase 4 before the ruling either — `OPS-005` already had
hosted-only Windows findings not gating a phase — so this records the intent rather than
changing a gate. Phase 5 is where it genuinely bites: the release needs a Windows artifact that
installs and runs.)*
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
**Phase:** Phase 1 origin; it is an instrument, not a deliverable, and gates no exit *(**Reassigned to Phase 5 on 2026-09-10 by maintainer ruling**, with the other Windows-only
tasks: *"defer the windows specific screen tasks to the same phase. They should no longer block
phase 4 closure."* It did not block Phase 4 before the ruling either — `OPS-005` already had
hosted-only Windows findings not gating a phase — so this records the intent rather than
changing a gate. Phase 5 is where it genuinely bites: the release needs a Windows artifact that
installs and runs.)*
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
**Phase:** Phase 1 *(**Reassigned to Phase 5 on 2026-09-10 by maintainer ruling**, with the other Windows-only
tasks: *"defer the windows specific screen tasks to the same phase. They should no longer block
phase 4 closure."* It did not block Phase 4 before the ruling either — `OPS-005` already had
hosted-only Windows findings not gating a phase — so this records the intent rather than
changing a gate. Phase 5 is where it genuinely bites: the release needs a Windows artifact that
installs and runs.)*
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
**Phase:** Phase 1 *(**Reassigned to Phase 5 on 2026-09-10 by maintainer ruling**, with the other Windows-only
tasks: *"defer the windows specific screen tasks to the same phase. They should no longer block
phase 4 closure."* It did not block Phase 4 before the ruling either — `OPS-005` already had
hosted-only Windows findings not gating a phase — so this records the intent rather than
changing a gate. Phase 5 is where it genuinely bites: the release needs a Windows artifact that
installs and runs.)*
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
